"""
Application entrypoint — bootstraps all SDK services and wires them into FastAPI's app.state.

Service map (what routes expect → what we inject here):
    auth_service      ← PlatformAuthService (JWTService + PasswordService + UserRepo)
    user_service      ← PlatformUserService (UserRepo + APIKeyService)
    workflow_service  ← PlatformWorkflowService (WorkflowRepo)
    execution_service ← PlatformExecutionService (ExecutionRepo + Celery dispatch)
    schedule_service  ← PlatformScheduleService (ScheduleRepo)
    audit_service     ← PlatformAuditService (MongoDB audit_log collection)
    webhook_service   ← PlatformWebhookService (stub — no DB table yet)
    billing_service   ← PlatformBillingService (BillingRepo)
    chat_orchestrator ← ChatOrchestrator (LLM + ConversationRepo + WorkflowRepo)
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import FastAPI

from workflow_api.app import create_app

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Service Facades
# Thin adapters between route handlers and SDK low-level primitives.
# Routes call high-level methods; facades delegate to the correct SDK service.
# ─────────────────────────────────────────────────────────────────────────────

class PlatformAuthService:
    """Coordinates JWTService + PasswordService + UserRepository for /auth routes."""

    def __init__(self, jwt_svc: Any, pwd_svc: Any, user_repo: Any) -> None:
        self._jwt = jwt_svc
        self._pwd = pwd_svc
        self._users = user_repo

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Called by dependencies.py on every authenticated request."""
        if token.startswith("wfk_"):
            import hashlib
            key_hash = hashlib.sha256(token.encode()).hexdigest()
            row = await self._users._pool.fetchrow(
                "SELECT ak.user_id, u.email, u.role, u.tenant_id "
                "FROM api_keys ak JOIN users u ON ak.user_id = u.id "
                "WHERE ak.key_hash = $1 AND ak.is_active = true "
                "AND (ak.expires_at IS NULL OR ak.expires_at > NOW())",
                key_hash,
            )
            if not row:
                raise ValueError("Invalid or expired API key")
            return {
                "id": str(row["user_id"]),
                "email": row["email"],
                "role": row["role"],
                "tenant_id": str(row["tenant_id"]),
            }

        claims = self._jwt.verify_access_token(token)
        row = await self._users._pool.fetchrow(
            "SELECT id, email, role, tenant_id FROM users WHERE id = $1",
            claims.user_id,
        )
        if not row:
            raise ValueError("User not found")
        return {
            "id": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
            "tenant_id": str(row["tenant_id"]),
        }

    async def register(self, email: str, password: str, full_name: str | None = None) -> dict:
        strength = self._pwd.validate_strength(password)
        if not strength.is_valid:
            raise ValueError(", ".join(strength.errors))

        existing = await self._users.get_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        user_id = str(uuid.uuid4())
        tenant_id = str(uuid.uuid4())
        hashed = self._pwd.hash(password)
        # slug: lowercase email local part, sanitised (e.g. "alice@example.com" → "alice-<8hex>")
        slug = email.split("@")[0].lower().replace(".", "-") + "-" + uuid.uuid4().hex[:8]

        await self._users._pool.execute(
            "INSERT INTO tenants (id, name, slug, plan_tier, created_at) VALUES ($1, $2, $3, 'FREE', NOW())",
            tenant_id, email, slug,
        )
        await self._users._pool.execute(
            # users table has no full_name column — role enum is OWNER/EDITOR/VIEWER
            "INSERT INTO users (id, email, password_hash, role, tenant_id, mfa_enabled, created_at) "
            "VALUES ($1, $2, $3, 'OWNER', $4, false, NOW())",
            user_id, email.lower(), hashed, tenant_id,
        )
        return {"id": user_id, "email": email}

    async def login(self, email: str, password: str) -> dict:
        row = await self._users._pool.fetchrow(
            "SELECT id, password_hash, role, tenant_id FROM users WHERE email = $1",
            email.lower(),
        )
        if not row or not self._pwd.verify(password, row["password_hash"]):
            raise ValueError("Invalid credentials")

        from workflow_engine.auth.models import Role
        access = self._jwt.issue_access_token(
            str(row["id"]), str(row["tenant_id"]), [Role(row["role"])]
        )
        refresh = self._jwt.issue_refresh_token(str(row["id"]))
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": 900}

    async def logout(self, token: str) -> None:
        # Stateless JWT v1 — tokens expire naturally (15 min).
        # Redis JTI blocklist for immediate revocation is a v2 feature.
        pass

    async def refresh(self, refresh_token: str) -> dict:
        claims = self._jwt.verify_refresh_token(refresh_token)
        row = await self._users._pool.fetchrow(
            "SELECT role, tenant_id FROM users WHERE id = $1", claims.user_id
        )
        if not row:
            raise ValueError("User not found")
        from workflow_engine.auth.models import Role
        new_access, new_refresh = self._jwt.rotate_refresh_token(
            refresh_token, str(row["tenant_id"]), [Role(row["role"])]
        )
        return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer", "expires_in": 900}

    async def verify_email(self, token: str) -> None:
        pass  # v1: feature-flagged off — requires email/SMTP integration

    async def send_password_reset(self, email: str) -> None:
        pass  # v1: requires SMTP/SES — stub logs and returns silently

    async def reset_password(self, token: str, new_password: str) -> None:
        pass  # v1: requires password_reset_tokens table flow

    async def mfa_setup(self, user_id: str) -> dict:
        return {"enabled": False, "message": "MFA feature-flagged off in v1"}

    async def mfa_verify(self, user_id: str, code: str) -> dict:
        return {"verified": False, "message": "MFA feature-flagged off in v1"}

    async def oauth_redirect_url(self, provider: str) -> str:
        raise NotImplementedError(f"OAuth provider '{provider}' not configured in v1")

    async def oauth_exchange(self, provider: str, code: str) -> dict:
        raise NotImplementedError(f"OAuth provider '{provider}' not configured in v1")


class PlatformUserService:
    def __init__(self, user_repo: Any) -> None:
        self._users = user_repo

    async def get_profile(self, user_id: str) -> dict:
        row = await self._users._pool.fetchrow(
            "SELECT id, email, role, mfa_enabled, created_at FROM users WHERE id = $1",
            user_id,
        )
        if not row:
            raise ValueError("User not found")
        return {
            "id": str(row["id"]),
            "email": row["email"],
            "role": row["role"],
            "mfa_enabled": row["mfa_enabled"],
        }

    async def update_profile(self, user_id: str, data: dict) -> dict:
        # users table has no full_name/avatar_url columns — no-op for now;
        # these would require an ALTER TABLE migration to add profile columns.
        return await self.get_profile(user_id)

    async def list_api_keys(self, user_id: str) -> list:
        # Schema columns: id, key_prefix, key_hash, scopes, is_active, expires_at, created_at
        rows = await self._users._pool.fetch(
            "SELECT id, name, key_prefix, scopes, created_at, expires_at "
            "FROM api_keys WHERE user_id = $1 AND is_active = true ORDER BY created_at DESC",
            user_id,
        )
        return [
            {
                "key_id": str(r["id"]),
                "name": r["name"],
                "prefix": r["key_prefix"],
                "scopes": list(r["scopes"]),
                "created_at": r["created_at"].isoformat(),
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
            }
            for r in rows
        ]

    async def create_api_key(
        self, user_id: str, name: str, scopes: list, expires_in_days: int | None
    ) -> dict:
        from workflow_engine.auth.api_key_service import APIKeyService
        row = await self._users._pool.fetchrow(
            "SELECT tenant_id FROM users WHERE id = $1", user_id
        )
        raw_key, record = APIKeyService.create(str(row["tenant_id"]), name, scopes)
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(tz=timezone.utc) + timedelta(days=expires_in_days)
        # Schema columns: id, tenant_id, user_id, name, key_prefix, key_hash, scopes, is_active
        await self._users._pool.execute(
            "INSERT INTO api_keys "
            "(id, tenant_id, user_id, name, key_prefix, key_hash, scopes, expires_at, is_active, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7::text[], $8, true, NOW())",
            record.key_id, str(row["tenant_id"]), user_id, name,
            record.prefix, record.key_hash, scopes, expires_at,
        )
        return {
            "key_id": record.key_id, "name": name, "key": raw_key,
            "prefix": record.prefix, "scopes": scopes,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }

    async def delete_api_key(self, user_id: str, key_id: str) -> None:
        await self._users._pool.execute(
            "UPDATE api_keys SET is_active = false WHERE id = $1 AND user_id = $2",
            key_id, user_id,
        )


class PlatformWorkflowService:
    def __init__(self, workflow_repo: Any) -> None:
        self._repo = workflow_repo

    async def list(self, tenant_id: str, skip: int = 0, limit: int = 20) -> list:
        items = await self._repo.list(tenant_id, skip=skip, limit=limit)
        return [w.model_dump(mode="json") for w in items]

    async def create(self, tenant_id: str, data: dict) -> dict:
        from workflow_engine.models import WorkflowDefinition
        raw_def = data.get("definition") or {}
        raw_nodes = raw_def.get("nodes") or {}
        # Accept either a list (UI sends []) or dict — normalize to empty dict if list
        if isinstance(raw_nodes, list):
            raw_nodes = {}
        wf = WorkflowDefinition(
            id=str(uuid.uuid4()),
            name=data.get("name", "Untitled"),
            description=data.get("description"),
            nodes=raw_nodes,
            edges=raw_def.get("edges") or [],
        )
        created = await self._repo.create(tenant_id, wf)
        return created.model_dump(mode="json")

    async def get(self, tenant_id: str, workflow_id: str) -> dict | None:
        wf = await self._repo.get(tenant_id, workflow_id)
        return wf.model_dump(mode="json") if wf else None

    async def update(self, tenant_id: str, workflow_id: str, data: dict) -> dict:
        wf = await self._repo.get(tenant_id, workflow_id)
        if not wf:
            raise ValueError("Workflow not found")
        from workflow_engine.models import WorkflowDefinition
        merged = {**wf.model_dump(mode="json"), **data}
        updated = WorkflowDefinition.model_validate(merged)
        result = await self._repo.update(tenant_id, workflow_id, updated)
        return result.model_dump(mode="json")

    async def delete(self, tenant_id: str, workflow_id: str) -> None:
        await self._repo.delete(tenant_id, workflow_id)

    async def set_active(self, tenant_id: str, workflow_id: str, active: bool) -> dict:
        return await self.update(tenant_id, workflow_id, {"is_active": active})

    async def list_versions(self, tenant_id: str, workflow_id: str) -> list:
        return []  # Versioning repo not in RepositoryBundle yet — v2 feature

    async def get_version(self, tenant_id: str, workflow_id: str, version_no: int) -> dict:
        from fastapi import HTTPException
        raise HTTPException(status_code=501, detail="Versioning not yet implemented")

    async def restore_version(self, tenant_id: str, workflow_id: str, version_no: int) -> dict:
        from fastapi import HTTPException
        raise HTTPException(status_code=501, detail="Versioning not yet implemented")


class PlatformExecutionService:
    def __init__(self, execution_repo: Any, workflow_repo: Any) -> None:
        self._executions = execution_repo
        self._workflows = workflow_repo

    async def trigger(
        self, tenant_id: str, workflow_id: str, input_data: dict,
        triggered_by: str | None = None
    ) -> dict:
        from workflow_engine.models import ExecutionRun
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        run = ExecutionRun(
            run_id=run_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status="QUEUED",
            input_data=input_data,
            started_at=datetime.now(tz=timezone.utc),
            node_states={},
        )
        await self._executions.create(tenant_id, run)
        try:
            from workflow_worker.tasks import execute_workflow
            execute_workflow.delay(run_id, tenant_id, workflow_id, input_data)
        except ImportError:
            logger.warning("workflow_worker not available — run queued in DB but not dispatched")
        return {"run_id": run_id, "status": "QUEUED"}

    async def list(
        self, tenant_id: str, workflow_id: str | None = None,
        skip: int = 0, limit: int = 20
    ) -> list:
        items = await self._executions.list(tenant_id, workflow_id=workflow_id, skip=skip, limit=limit)
        return [r.model_dump(mode="json") for r in items]

    async def get(self, tenant_id: str, run_id: str) -> dict | None:
        run = await self._executions.get(tenant_id, run_id)
        return run.model_dump(mode="json") if run else None

    async def cancel(self, tenant_id: str, run_id: str) -> dict:
        run = await self._executions.get(tenant_id, run_id)
        if not run:
            raise ValueError("Run not found")
        run.status = "CANCELLED"  # type: ignore[misc]
        await self._executions.update_state(tenant_id, run_id, run)
        return {"run_id": run_id, "status": "CANCELLED"}

    async def retry(self, tenant_id: str, run_id: str) -> dict:
        run = await self._executions.get(tenant_id, run_id)
        if not run:
            raise ValueError("Run not found")
        return await self.trigger(tenant_id, run.workflow_id, run.input_data or {})

    async def list_nodes(self, tenant_id: str, run_id: str) -> list:
        run = await self._executions.get(tenant_id, run_id)
        if not run:
            return []
        return [{"node_id": k, **v} for k, v in (run.node_states or {}).items()]

    async def submit_human_input(
        self, tenant_id: str, run_id: str, node_id: str, response: dict
    ) -> dict:
        run = await self._executions.get(tenant_id, run_id)
        if not run:
            raise ValueError("Run not found")
        if run.status != "WAITING_HUMAN":
            raise ValueError(f"Run is not paused for human input (status: {run.status})")
        try:
            from workflow_worker.tasks import execute_workflow
            execute_workflow.apply_async(
                args=[run_id, tenant_id, run.workflow_id, {}],
                kwargs={"resume_node": node_id, "human_response": response},
            )
        except ImportError:
            logger.warning("workflow_worker not available — human input recorded, resume not dispatched")
        return {"run_id": run_id, "node_id": node_id, "accepted": True}

    async def get_logs(self, tenant_id: str, run_id: str, skip: int = 0, limit: int = 100) -> list:
        run = await self._executions.get(tenant_id, run_id)
        if not run:
            return []
        logs: list[dict] = []
        for node_id, state in (run.node_states or {}).items():
            for msg in state.get("logs", []):
                logs.append({"node_id": node_id, "message": msg, "run_id": run_id})
        return logs[skip: skip + limit]


class PlatformScheduleService:
    def __init__(self, schedule_repo: Any) -> None:
        self._repo = schedule_repo

    async def list(self, tenant_id: str, workflow_id: str) -> list:
        cursor = self._repo._collection.find(
            {"tenant_id": tenant_id, "workflow_id": workflow_id}
        )
        docs = []
        async for doc in cursor:
            doc.pop("_id", None)
            docs.append(doc)
        return docs

    async def create(self, tenant_id: str, workflow_id: str, data: dict) -> dict:
        from workflow_engine.models import ScheduleModel
        schedule = ScheduleModel(
            schedule_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            cron_expression=data.get("cron_expression", "0 * * * *"),
            timezone=data.get("timezone", "UTC"),
            is_active=True,
        )
        result = await self._repo.create(tenant_id, schedule)
        return result.model_dump(mode="json")

    async def get(self, tenant_id: str, schedule_id: str) -> dict | None:
        s = await self._repo.get(tenant_id, schedule_id)
        return s.model_dump(mode="json") if s else None

    async def update(self, tenant_id: str, schedule_id: str, data: dict) -> dict:
        s = await self._repo.get(tenant_id, schedule_id)
        if not s:
            raise ValueError("Schedule not found")
        from workflow_engine.models import ScheduleModel
        updated = ScheduleModel.model_validate({**s.model_dump(mode="json"), **data})
        result = await self._repo.update(tenant_id, schedule_id, updated)
        return result.model_dump(mode="json")

    async def delete(self, tenant_id: str, schedule_id: str) -> None:
        await self._repo._collection.delete_one(
            {"tenant_id": tenant_id, "schedule_id": schedule_id}
        )


class PlatformAuditService:
    """Reads from MongoDB audit_log collection. No typed AuditRepository in RepositoryBundle yet."""

    def __init__(self, mongo_db: Any) -> None:
        self._col = mongo_db["audit_log"]

    async def list(self, tenant_id: str, skip: int = 0, limit: int = 50) -> list:
        cursor = self._col.find({"tenant_id": tenant_id}).sort("created_at", -1).skip(skip).limit(limit)
        docs = []
        async for doc in cursor:
            doc.pop("_id", None)
            docs.append(doc)
        return docs


class PlatformWebhookService:
    """Stub — no webhook table in the DB schema yet. Returns safe empty responses."""

    async def list(self, tenant_id: str) -> list:
        return []

    async def create(self, tenant_id: str, data: dict) -> dict:
        return {**data, "webhook_id": str(uuid.uuid4()), "tenant_id": tenant_id, "active": True}

    async def get(self, tenant_id: str, webhook_id: str) -> dict | None:
        return None

    async def update(self, tenant_id: str, webhook_id: str, data: dict) -> dict:
        return {**data, "webhook_id": webhook_id}

    async def delete(self, tenant_id: str, webhook_id: str) -> None:
        pass

    async def handle_inbound(self, workflow_id: str, body: dict, signature: str) -> dict:
        return {"accepted": True, "workflow_id": workflow_id}


class PlatformBillingService:
    def __init__(self, billing_repo: Any) -> None:
        self._repo = billing_repo

    async def get_usage_summary(self, tenant_id: str) -> dict:
        from datetime import date
        today = date.today()
        count = await self._repo.get_monthly_run_count(tenant_id, today.year, today.month)
        return {
            "tenant_id": tenant_id,
            "period": f"{today.year}-{today.month:02d}",
            "execution_count": count,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Application Lifespan
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from workflow_engine.config import LLMProvidersConfig
    from workflow_engine.storage.factory import RepositoryFactory
    from workflow_engine.auth.jwt_service import JWTService
    from workflow_engine.auth.password_service import PasswordService
    from workflow_engine.chat.orchestrator import ChatOrchestrator
    from workflow_engine.chat.dag_generator import DAGGeneratorService
    from workflow_engine.chat.requirement_extractor import RequirementExtractor
    from workflow_engine.chat.clarification_engine import ClarificationEngine
    from workflow_engine.cache.cached_llm import CachedLLMProvider
    from workflow_engine.cache.redis_cache import RedisCache
    from workflow_engine.cache.key_builder import CacheKeyBuilder
    from workflow_engine.providers.factory import ProviderFactory
    import redis.asyncio as aioredis

    logger.info("Starting DK Workflow API...")

    # Use sub-configs directly so EngineConfig.tenant (which requires TENANT_ID,
    # a per-request value) does not block global startup.
    from workflow_engine.config import StorageConfig
    storage_config = StorageConfig()
    llm_config = LLMProvidersConfig()

    # 1. Storage — connection pools (PostgreSQL + MongoDB + S3)
    # RepositoryFactory.create_all() accesses config.mongodb_url / .postgres_url
    # directly, which live on StorageConfig — pass storage_config, not EngineConfig.
    repos = await RepositoryFactory.create_all(storage_config)

    # 2. LLM provider — select via LLM_PROVIDER env var (default: google)
    provider_name = os.getenv("LLM_PROVIDER", "google")
    llm = ProviderFactory.from_config(llm_config, provider_name=provider_name)

    # 3. Auth primitives
    # Supports two env-var styles:
    #   - JWT_PRIVATE_KEY / JWT_PUBLIC_KEY  (raw PEM string, used in K8s/prod)
    #   - JWT_PRIVATE_KEY_PATH / JWT_PUBLIC_KEY_PATH  (file path, used locally)
    def _read_key(env_key: str, path_env: str) -> str:
        if val := os.environ.get(env_key):
            return val.replace("\\n", "\n")
        if path := os.environ.get(path_env):
            from pathlib import Path
            return Path(path).read_text(encoding="utf-8")
        raise RuntimeError(f"Neither {env_key} nor {path_env} is set in the environment")

    jwt_svc = JWTService(
        private_key=_read_key("JWT_PRIVATE_KEY", "JWT_PRIVATE_KEY_PATH"),
        public_key=_read_key("JWT_PUBLIC_KEY", "JWT_PUBLIC_KEY_PATH"),
        refresh_secret=os.environ["JWT_REFRESH_SECRET"],
    )
    pwd_svc = PasswordService()

    # 4. Chat orchestrator — wire Redis cache + LLM components
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_client = await aioredis.from_url(redis_url, decode_responses=True)
    redis_cache = RedisCache(client=redis_client)
    key_builder = CacheKeyBuilder(tenant_id="system", namespace="chat")
    cached_llm = CachedLLMProvider(provider=llm, redis_cache=redis_cache, key_builder=key_builder)

    dag_svc = DAGGeneratorService(cached_llm)
    extractor = RequirementExtractor(cached_llm)
    clarifier = ClarificationEngine(cached_llm)
    chat_orch = ChatOrchestrator(
        repo=repos.chat_sessions,
        workflow_repo=repos.workflows,
        extractor=extractor,
        clarifier=clarifier,
        generator=dag_svc,
    )

    # 5. Raw Motor DB handle — needed for audit_log (no typed repo in bundle yet)
    mongo_db = repos.workflows._collection.database

    # 6. Wire all services onto app.state
    services: dict[str, Any] = {
        "auth_service":      PlatformAuthService(jwt_svc, pwd_svc, repos.users),
        "user_service":      PlatformUserService(repos.users),
        "workflow_service":  PlatformWorkflowService(repos.workflows),
        "execution_service": PlatformExecutionService(repos.executions, repos.workflows),
        "schedule_service":  PlatformScheduleService(repos.schedules),
        "audit_service":     PlatformAuditService(mongo_db),
        "webhook_service":   PlatformWebhookService(),
        "billing_service":   PlatformBillingService(repos.billing),
        "chat_orchestrator": chat_orch,
        "repos":             repos,
    }
    for name, svc in services.items():
        setattr(app.state, name, svc)

    logger.info("API startup complete — %d services wired to app.state.", len(services))
    yield

    # Graceful shutdown — close connection pools
    logger.info("Shutting down API — closing connection pools...")
    try:
        await repos.users._pool.close()
        logger.info("PostgreSQL pool closed.")
    except Exception as exc:
        logger.warning("Error closing PostgreSQL pool: %s", exc)
    try:
        repos.workflows._collection.database.client.close()
        logger.info("MongoDB client closed.")
    except Exception as exc:
        logger.warning("Error closing MongoDB client: %s", exc)
    try:
        await redis_client.aclose()
        logger.info("Redis client closed.")
    except Exception as exc:
        logger.warning("Error closing Redis client: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# App instance (consumed by uvicorn / gunicorn in Dockerfile CMD)
# ─────────────────────────────────────────────────────────────────────────────

app = create_app()
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
