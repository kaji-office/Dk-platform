"""
conftest.py — shared pytest fixtures and configuration.
Isolates test imports so heavy provider SDKs are not loaded at collection time.
"""
import sys
from pathlib import Path

# Ensure src/ is on the path for direct `python -m pytest` invocations
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest
from unittest.mock import AsyncMock, MagicMock
from workflow_engine.models.tenant import TenantConfig, PlanTier
from workflow_engine.nodes.base import NodeServices
from workflow_engine.ports import BillingRepository, ExecutionRepository, TenantRepository, UserRepository

@pytest.fixture
def mock_tenant_config() -> TenantConfig:
    return TenantConfig(
        tenant_id="tenant-123",
        plan_tier=PlanTier.PRO,
        api_keys={"openai": "sk-mock"}
    )

@pytest.fixture
def mock_node_services() -> NodeServices:
    mock_storage = MagicMock()
    # Mock download_data resolving some string payload
    mock_storage.download_data = AsyncMock(return_value=b'{"mock": "data"}')
    mock_storage.upload_data = AsyncMock(return_value="s3://mock-bucket/obj")
    
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value="Mock LLM response")
    mock_llm.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])

    return NodeServices(storage=mock_storage, llm=mock_llm)

@pytest.fixture
def mock_billing_repo() -> MagicMock:
    repo = MagicMock(spec=BillingRepository)
    repo.get_monthly_run_count = AsyncMock(return_value=10)
    repo.get_usage_summary = AsyncMock(return_value={})
    return repo

@pytest.fixture
def mock_execution_repo() -> MagicMock:
    repo = MagicMock(spec=ExecutionRepository)
    repo.get = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value="run-123")
    repo.update_state = AsyncMock(return_value=None)
    return repo
