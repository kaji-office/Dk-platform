"""Tests for the C-1 Execution Engine module."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from workflow_engine.errors import NodeExecutionError, PIIBlockedError
from workflow_engine.execution import (
    ContextManager, PIIScanner, RetryConfig, RetryHandler, 
    StateMachine, StateTransitionError, TimeoutManager
)
from workflow_engine.models import ExecutionRun, RunStatus, TenantConfig
from workflow_engine.models.tenant import PIIPolicy
from workflow_engine.ports import ExecutionRepository, CachePort


class MockRepo(ExecutionRepository):
    def __init__(self):
        self.runs = {}

    async def get(self, tenant_id: str, run_id: str) -> ExecutionRun | None:
        return self.runs.get(run_id)

    async def create(self, tenant_id: str, execution: ExecutionRun) -> ExecutionRun:
        self.runs[execution.run_id] = execution
        return execution

    async def update_state(self, tenant_id: str, run_id: str, execution: ExecutionRun) -> ExecutionRun:
        self.runs[run_id] = execution
        return execution

    async def list(self, tenant_id: str, workflow_id: str | None = None, skip: int = 0, limit: int = 100) -> list[ExecutionRun]:
        return list(self.runs.values())


@pytest.mark.asyncio
async def test_state_machine_valid_transition():
    repo = MockRepo()
    repo.runs["run-1"] = ExecutionRun(
        run_id="run-1", workflow_id="wf-1", tenant_id="tt", status=RunStatus.QUEUED
    )
    
    run = await StateMachine.transition_run(repo, "tt", "run-1", RunStatus.RUNNING)
    assert run.status == RunStatus.RUNNING


@pytest.mark.asyncio
async def test_state_machine_invalid_transition():
    repo = MockRepo()
    repo.runs["run-1"] = ExecutionRun(
        run_id="run-1", workflow_id="wf-1", tenant_id="tt", status=RunStatus.SUCCESS
    )
    
    with pytest.raises(StateTransitionError):
        await StateMachine.transition_run(repo, "tt", "run-1", RunStatus.RUNNING)


def test_pii_scanner_block_ssn():
    config = TenantConfig(tenant_id="t1", pii_policy=PIIPolicy.SCAN_BLOCK)
    data = {"user": "John Doe", "ssn": "123-45-6789", "history": [{"credit_card": "4111222233334444"}]}
    
    with pytest.raises(PIIBlockedError, match="SSN"):
        PIIScanner.scan_dict(data, config)


def test_pii_scanner_allow():
    config = TenantConfig(tenant_id="t1", pii_policy=PIIPolicy.SCAN_WARN)
    data = {"ssn": "123-45-6789"}
    # Should not raise exception
    PIIScanner.scan_dict(data, config)


@pytest.mark.asyncio
async def test_retry_handler():
    calls = 0
    async def failable_task():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("Boom")
        return "SUCCESS"

    config = RetryConfig(max_attempts=3, initial_delay_seconds=0.01, jitter=False)
    # Using 0.01 delay for fast test execution
    
    result = await RetryHandler.execute_with_retry(failable_task.__call__, config)
    assert result == "SUCCESS"
    assert calls == 3


@pytest.mark.asyncio
async def test_timeout_manager():
    async def slow_task():
        await asyncio.sleep(0.5)
        return "DONE"

    with pytest.raises(NodeExecutionError, match="exceeded timeout"):
        await TimeoutManager.wrap(slow_task(), 0.1, "node1")


@pytest.mark.asyncio
async def test_context_manager_inline():
    cm = ContextManager("run1", None)
    out = await cm.store_output("t1", "n1", {"foo": "bar"})
    assert out == {"foo": "bar"}


@pytest.mark.asyncio
async def test_context_manager_blob():
    storage = AsyncMock()
    storage.upload = AsyncMock()
    cm = ContextManager("run1", storage)
    
    # 100K bytes
    huge_payload = {"data": "x" * 100000}
    
    out = await cm.store_output("t1", "n1", huge_payload)
    assert "__blob" in out
    storage.upload.assert_called_once()
