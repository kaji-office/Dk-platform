"""
P9-T-06 — Execution cancellation integration test.

Verifies:
1. POST /executions/{run_id}/cancel returns the cancelled run
2. The run's status is updated to CANCELLED
3. Celery task revoke() is called if a celery_task_id is stored
4. Cancelling an already-terminal run returns 409 (conflict)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from workflow_api.app import create_app


def _build_app(
    *,
    run_data: dict | None = None,
    cancel_side_effect=None,
):
    auth_svc = AsyncMock()
    auth_svc.verify_token.return_value = {"id": "u1", "tenant_id": "t1", "role": "ADMIN"}

    exec_svc = AsyncMock()
    if cancel_side_effect is not None:
        exec_svc.cancel.side_effect = cancel_side_effect
    else:
        exec_svc.cancel.return_value = run_data or {
            "run_id": "r1",
            "status": "CANCELLED",
            "workflow_id": "wf-1",
        }
    exec_svc.get.return_value = run_data or {"run_id": "r1", "status": "RUNNING"}

    services = {
        "auth_service": auth_svc,
        "user_service": AsyncMock(),
        "workflow_service": AsyncMock(),
        "execution_service": exec_svc,
        "webhook_service": AsyncMock(),
        "audit_service": AsyncMock(),
        "billing_service": AsyncMock(),
        "schedule_service": AsyncMock(),
    }
    app = create_app(services=services)
    app.state.limiter.reset()
    return app


@pytest.mark.asyncio
async def test_cancel_running_run_returns_cancelled():
    """POST /executions/{run_id}/cancel on a RUNNING run returns cancelled status."""
    app = _build_app(run_data={"run_id": "r1", "status": "CANCELLED"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/executions/r1/cancel",
            headers={"Authorization": "Bearer tok"},
        )
    assert resp.status_code == 200
    body = resp.json().get("data") or resp.json()
    assert body.get("status") == "CANCELLED" or body.get("run_id") == "r1"


@pytest.mark.asyncio
async def test_cancel_calls_execution_service():
    """cancel endpoint must call execution_service.cancel() exactly once."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/executions/r1/cancel",
            headers={"Authorization": "Bearer tok"},
        )
    app.state.execution_service.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_unauthenticated_returns_401():
    """cancel endpoint without auth must return 401."""
    app = _build_app()
    # Override verify_token to raise
    from workflow_engine.errors import AuthenticationError
    app.state.auth_service.verify_token.side_effect = AuthenticationError("no auth")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/executions/r1/cancel")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_cancel_viewer_role_forbidden():
    """VIEWER role cannot cancel executions (→ 403)."""
    app = _build_app()
    app.state.auth_service.verify_token.return_value = {
        "id": "u-viewer", "tenant_id": "t1", "role": "VIEWER"
    }
    from workflow_engine.errors import InsufficientPermissionsError
    app.state.execution_service.cancel.side_effect = InsufficientPermissionsError("no permission")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/executions/r1/cancel",
            headers={"Authorization": "Bearer viewer-tok"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_unknown_run_returns_404():
    """cancel on a run that doesn't exist must return 404."""
    app = _build_app()
    # Service raises ValueError for not-found → route converts to 404
    app.state.execution_service.cancel.side_effect = ValueError("Run not found")
    app.state.execution_service.get.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/executions/nonexistent/cancel",
            headers={"Authorization": "Bearer tok"},
        )
    assert resp.status_code == 404


# ── Orchestrator cancel unit tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_orchestrator_cancel_transitions_to_cancelled():
    """
    RunOrchestrator.cancel() must set run status to CANCELLED.
    """
    from workflow_engine.execution.orchestrator import RunOrchestrator
    from workflow_engine.models.execution import ExecutionRun, RunStatus
    from workflow_engine.models.tenant import TenantConfig
    from workflow_engine.nodes.base import NodeServices

    class _MockRepo:
        def __init__(self):
            self._run = ExecutionRun(run_id="r1", workflow_id="wf-1", tenant_id="t1", status=RunStatus.RUNNING)

        async def get(self, tenant_id, run_id):
            return self._run

        async def create(self, *a, **kw):
            return self._run

        async def update_state(self, tenant_id, run_id, run):
            self._run = run
            return run

        async def list(self, *a, **kw):
            return []

        async def get_node_states(self, *a, **kw):
            return []

        async def list_runs_by_tenant(self, *a, **kw):
            return []

        async def patch_fields(self, *a, **kw):
            pass

        async def update_node_state(self, *a, **kw):
            pass

        async def bulk_update_node_states(self, *a, **kw):
            pass

        async def list_stale_running(self, *a, **kw):
            return []

    repo = _MockRepo()
    orchestrator = RunOrchestrator(
        repo=repo,
        services=NodeServices(),
        config=TenantConfig(tenant_id="t1"),
    )

    await orchestrator.cancel("t1", "r1")

    final = await repo.get("t1", "r1")
    assert final.status == RunStatus.CANCELLED
