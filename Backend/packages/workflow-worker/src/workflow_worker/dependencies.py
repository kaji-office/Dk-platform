"""
Asynchronous SDK Injection for Celery Worker tasks.
"""
from typing import Any
import os
import asyncio
from workflow_engine.models.tenant import TenantConfig, PlanTier
from workflow_engine.execution.orchestrator import RunOrchestrator
from workflow_engine.nodes import NodeServices

# Store singletons per worker process
_sdk: dict[str, Any] | None = None
_loop: asyncio.AbstractEventLoop | None = None

# Plan-tier defaults for execution quotas
_PLAN_QUOTAS: dict[str, dict[str, int]] = {
    PlanTier.FREE:       {"timeout_seconds": 300,  "max_nodes": 10},
    PlanTier.STARTER:    {"timeout_seconds": 600,  "max_nodes": 25},
    PlanTier.PRO:        {"timeout_seconds": 1800, "max_nodes": 50},
    PlanTier.ENTERPRISE: {"timeout_seconds": 3600, "max_nodes": 200},
}

_TENANT_CONFIG_TTL = 300  # seconds

class ConnectionErrorRetryable(Exception):
    """Wrapper for transient connection errors to tell Celery to retry."""
    pass

async def get_tenant_config(sdk: dict[str, Any], tenant_id: str) -> TenantConfig:
    """
    Fetch per-tenant config from Postgres, cached in Redis for 5 minutes.
    Falls back to FREE-tier defaults if tenant is not found.
    """
    import json as _json
    redis_client = sdk.get("redis_client")
    cache_key = f"tenant_config:{tenant_id}"

    if redis_client is not None:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                data = _json.loads(cached)
                return TenantConfig(**data)
        except Exception:
            pass

    # Fetch from Postgres via user_repo pool
    pool = sdk["user_repo_pool"]
    row = None
    try:
        row = await pool.fetchrow(
            "SELECT plan_tier FROM tenants WHERE id = $1::uuid", tenant_id
        )
    except Exception:
        pass

    plan = PlanTier(row["plan_tier"]) if row else PlanTier.FREE
    quotas = _PLAN_QUOTAS.get(plan, _PLAN_QUOTAS[PlanTier.FREE])
    config = TenantConfig(tenant_id=tenant_id, plan_tier=plan, quotas=quotas)

    if redis_client is not None:
        try:
            await redis_client.setex(
                cache_key, _TENANT_CONFIG_TTL,
                _json.dumps(config.model_dump())
            )
        except Exception:
            pass

    return config

async def _health_check(sdk: dict[str, Any]) -> bool:
    """Ping MongoDB and PostgreSQL. Returns False if either is unreachable."""
    try:
        await sdk["execution_repo"]._collection.database.command("ping")
        pool = sdk.get("user_repo_pool")
        if pool is not None:
            await pool.fetchval("SELECT 1")
        return True
    except Exception:
        return False


async def get_engine() -> dict[str, Any]:
    """
    Lazily initializes shared resources (repos, services, Redis) in the CURRENT loop.
    NOTE: RunOrchestrator is NOT a singleton — it's built per-task with per-tenant config.

    Connection recovery: if the cached SDK fails a health check, it is discarded
    and re-initialized (up to 3 attempts with exponential backoff).
    """
    global _sdk
    if _sdk is not None:
        if await _health_check(_sdk):
            return _sdk
        import logging as _log
        _log.getLogger(__name__).warning("SDK health check failed — reinitializing connections")
        _sdk = None

    from workflow_engine.config import StorageConfig, LLMProvidersConfig
    from workflow_engine.storage.factory import RepositoryFactory
    from workflow_engine.providers.factory import ProviderFactory
    from workflow_engine.cache.redis_cache import RedisCache
    import redis.asyncio as aioredis
    import logging as _log

    _init_logger = _log.getLogger(__name__)

    storage_config = StorageConfig()
    llm_config = LLMProvidersConfig()

    # Retry initialization up to 3 times with exponential backoff
    for _attempt in range(1, 4):
        try:
            repos = await RepositoryFactory.create_all(storage_config)
            break
        except Exception as exc:
            if _attempt == 3:
                raise ConnectionErrorRetryable(f"Failed to initialize repos after 3 attempts: {exc}") from exc
            _delay = 2 ** _attempt
            _init_logger.warning("RepositoryFactory.create_all attempt %d failed: %s — retrying in %ds", _attempt, exc, _delay)
            await asyncio.sleep(_delay)

    provider_name = os.getenv("LLM_PROVIDER", "openai")
    valid_providers = {"openai", "google", "anthropic", "bedrock", "mock", "vertex"}
    if provider_name not in valid_providers:
        raise ValueError(
            f"Invalid LLM_PROVIDER={provider_name!r}. "
            f"Must be one of: {', '.join(sorted(valid_providers))}"
        )
    llm_port = ProviderFactory.from_config(llm_config, provider_name=provider_name)

    # Redis — required for SetStateNode state tracking + tenant config cache
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = await aioredis.from_url(redis_url, decode_responses=True)
    redis_cache = RedisCache(client=redis_client)

    services = NodeServices(
        storage=repos.storage,
        http_client=None,
        cache=redis_cache,
        llm=llm_port
    )

    # Minimal audit writer — writes to MongoDB audit_log collection directly
    from motor.motor_asyncio import AsyncIOMotorClient
    from workflow_engine.config import StorageConfig as _SC
    _sc = _SC()
    _mongo_client = AsyncIOMotorClient(_sc.mongodb_url)
    _db_name = _mongo_client.get_database().name or "dk_platform"
    _audit_col = _mongo_client[_db_name]["audit_log"]

    # Ensure TTL index exists — audit_log documents expire after 90 days.
    # create_index is idempotent: safe to call on every worker startup.
    try:
        await _audit_col.create_index(
            "created_at",
            expireAfterSeconds=90 * 24 * 60 * 60,  # 90 days
            name="idx_audit_log_ttl",
        )
    except Exception as _idx_exc:
        import logging as _log
        _log.getLogger(__name__).warning("audit_log TTL index creation failed: %s", _idx_exc)

    class _WorkerAuditService:
        async def write(self, tenant_id: str, event_type: str, detail: dict | None = None) -> None:
            from datetime import datetime, timezone
            try:
                await _audit_col.insert_one({
                    "tenant_id": tenant_id,
                    "event_type": event_type,
                    "user_id": "SYSTEM",
                    "resource_type": "task",
                    "resource_id": None,
                    "detail": detail or {},
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).error("Worker audit write failed: %s", exc)

    _sdk = {
        "services": services,
        "workflow_repo": repos.workflows,
        "execution_repo": repos.executions,
        "scheduler": repos.schedules,
        "audit": _WorkerAuditService(),
        "redis_client": redis_client,
        # Expose Postgres pool for per-tenant config lookup
        "user_repo_pool": repos.users._pool,
    }
    return _sdk


def build_orchestrator(sdk: dict[str, Any], tenant_config: TenantConfig) -> RunOrchestrator:
    """Build a RunOrchestrator scoped to a specific tenant config."""
    return RunOrchestrator(
        repo=sdk["execution_repo"],
        services=sdk["services"],
        config=tenant_config,
        redis_client=sdk.get("redis_client"),
    )

def run_async(coro) -> Any:
    """Helper to run async blocks in Celery tasks."""
    global _loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        loop = _loop
    
    return loop.run_until_complete(coro)
