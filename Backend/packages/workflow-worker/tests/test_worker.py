"""
Comprehensive Test Suite for the Celery Worker Layer (E-2).
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from celery.exceptions import Retry
from workflow_engine.errors import WorkflowValidationError
from workflow_worker.dependencies import ConnectionErrorRetryable

import workflow_worker.tasks as tasks
from workflow_worker.celery_app import app


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_sdk(monkeypatch):
    run_mock = MagicMock()
    run_mock.workflow_id = "test_wf"
    run_mock.trigger_input = {}
    
    execution_repo = MagicMock()
    execution_repo.get = AsyncMock(return_value=run_mock)

    workflow_repo = MagicMock()
    workflow_repo.get = AsyncMock(return_value=MagicMock())

    orchestrator = MagicMock()
    orchestrator.run = AsyncMock()

    audit = MagicMock()
    audit.create = AsyncMock(return_value=True)
    audit.write = AsyncMock(return_value=True)

    scheduler_repo = MagicMock()
    scheduler_repo.get_due_schedules = AsyncMock(return_value=[])

    sdk = {
        "execution_repo": execution_repo,
        "workflow_repo": workflow_repo,
        "orchestrator": orchestrator,
        "audit": audit,
        "redis_client": None,
        "scheduler": scheduler_repo,
    }

    # Intercept run_async to evaluate mocks easily
    def fake_run_async(coro):
        if hasattr(coro, "__await__"):
            import asyncio
            return asyncio.run(coro)
        return coro
    monkeypatch.setattr(tasks, "run_async", fake_run_async)

    async def mock_get_engine():
        return sdk

    monkeypatch.setattr(tasks, "get_engine", mock_get_engine)

    # Bypass build_orchestrator so tests can control orchestrator.run side effects
    monkeypatch.setattr(tasks, "build_orchestrator", lambda s, cfg: orchestrator)

    # Bypass get_tenant_config — no real DB in unit tests
    from workflow_engine.models.tenant import TenantConfig
    async def mock_get_tenant_config(s, tid):
        return TenantConfig(tenant_id=tid)
    monkeypatch.setattr(tasks, "get_tenant_config", mock_get_tenant_config)

    return sdk


class TestWorkerConfig:
    """AC: Worker drains gracefully on SIGTERM (60s window)"""

    def test_graceful_drain_config(self):
        assert app.conf.worker_proc_alive_timeout == 60.0
        assert app.conf.worker_cancel_long_running_tasks_on_connection_loss is True


class TestExecuteWorkflowRetries:
    """
    AC: Task retry on transient errors
    AC: Task does not retry on WorkflowValidationError
    """

    @patch("workflow_worker.tasks.handle_dlq")
    def test_no_retry_on_workflow_validation_error(self, mock_dlq, mock_sdk):
        mock_sdk["orchestrator"].run = AsyncMock(side_effect=WorkflowValidationError("Invalid node params"))
        
        result = tasks.execute_workflow.apply(args=("run1", "tenant1"))
        
        assert result.result is False
        mock_dlq.assert_called_once()
        args, kwargs = mock_dlq.call_args
        assert args[0] == "execute_workflow"
        assert args[1] == ["run1", "tenant1"]
        assert "Invalid node params" in args[2]["exc"]

    def test_retry_on_connection_error(self, mock_sdk):
        mock_sdk["orchestrator"].run = AsyncMock(side_effect=ConnectionErrorRetryable("DB Timeout"))
        
        result = tasks.execute_workflow.apply(args=("run1", "tenant1"))
        assert isinstance(result.result, ConnectionErrorRetryable)
        assert "DB Timeout" in str(result.result)


class TestFireSchedule:
    """AC: Celery beat fires schedules within ±5s of next_fire_at"""

    def test_beat_schedule_configured(self):
        schedule_conf = app.conf.beat_schedule.get("fire_schedule_every_30s")
        assert schedule_conf is not None
        assert schedule_conf["task"] == "workflow_worker.tasks.fire_schedule"
        assert schedule_conf["schedule"] == 30.0

    def test_fire_schedule_execution(self, mock_sdk):
        result = tasks.fire_schedule.apply()
        assert result.state == "SUCCESS"


class TestDeadLetterQueue:
    """AC: Dead letter queue handling — failed tasks → audit log"""

    def test_handle_dlq_logs_to_audit(self, mock_sdk):
        tasks.handle_dlq("test_task", ["arg1"], {"kwarg": "v"})

        mock_sdk["audit"].write.assert_called_once()
        call_kwargs = mock_sdk["audit"].write.call_args.kwargs
        assert call_kwargs["event_type"] == "task.failed"
        payload = call_kwargs["detail"]
        assert payload["task"] == "test_task"
        assert payload["args"] == ["arg1"]
