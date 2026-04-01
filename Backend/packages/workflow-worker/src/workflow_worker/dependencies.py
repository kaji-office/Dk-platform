"""
Asynchronous SDK Injection for Celery Worker tasks.
"""
from typing import Any
import os
import asyncio
from workflow_engine.models.tenant import TenantConfig
from workflow_engine.execution.orchestrator import RunOrchestrator
from workflow_engine.nodes import NodeServices
from workflow_engine.storage.s3_storage import S3StorageService

# Store singletons per worker process
_sdk: dict[str, Any] | None = None
_loop: asyncio.AbstractEventLoop | None = None

class ConnectionErrorRetryable(Exception):
    """Wrapper for transient connection errors to tell Celery to retry."""
    pass

async def get_engine() -> dict[str, Any]:
    """
    Lazily initializes the RunOrchestrator and repositories in the CURRENT loop.
    """
    global _sdk
    if _sdk is not None:
        return _sdk

    from workflow_engine.config import StorageConfig, LLMProvidersConfig
    from workflow_engine.storage.factory import RepositoryFactory
    from workflow_engine.providers.factory import ProviderFactory

    # Use StorageConfig directly — RepositoryFactory accesses config.mongodb_url /
    # .postgres_url which live on StorageConfig, not the nested EngineConfig.
    # EngineConfig.tenant also requires TENANT_ID (a per-request value), which
    # must not be a global startup requirement.
    storage_config = StorageConfig()
    llm_config = LLMProvidersConfig()
    repos = await RepositoryFactory.create_all(storage_config)
    llm_port = ProviderFactory.from_config(llm_config, provider_name="mock")

    tenant_config = TenantConfig(
        tenant_id="system", max_depth=10, timeout_seconds=3000,
        features={"caching": True}, memory_limit_mb=1024,
        allow_external_http=True
    )
    
    services = NodeServices(
        storage=repos.storage,
        http_client=None,
        cache=None,
        llm=llm_port
    )
    
    orchestrator = RunOrchestrator(
        repo=repos.executions,
        services=services,
        config=tenant_config
    )

    _sdk = {
        "orchestrator": orchestrator,
        "workflow_repo": repos.workflows,
        "execution_repo": repos.executions,
        "scheduler": repos.schedules,
        "audit": None
    }
    return _sdk

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
