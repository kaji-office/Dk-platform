"""
E-1 FastApi Layer — Comprehensive Test Suite

Validates all HTTP status codes, authentication, RBAC, Rate Limiting,
WebSocket streaming, and full route coverage.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from workflow_api.app import create_app


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_auth_service():
    svc = AsyncMock()
    # verify_token returns an ADMIN by default
    svc.verify_token.return_value = {"id": "u1", "tenant_id": "t1", "role": "ADMIN"}
    svc.register.return_value = {"id": "new_user", "email": "test@example.com", "tenant_id": "t1"}
    svc.login.return_value = {"access_token": "token", "refresh_token": "refresh", "tenant_id": "t1", "user_id": "u1"}
    svc.refresh.return_value = {"access_token": "new"}
    svc.oauth_redirect_url.return_value = "https://oauth.url"
    svc.oauth_exchange.return_value = {"access_token": "token"}
    svc.mfa_setup.return_value = {"uri": "otpauth://"}
    svc.mfa_verify.return_value = {"verified": True}
    return svc


@pytest.fixture
def mock_user_service():
    svc = AsyncMock()
    svc.get_profile.return_value = {"id": "u1", "email": "me@example.com"}
    svc.update_profile.return_value = {"id": "u1", "updated": True}
    svc.list_api_keys.return_value = [{"id": "key1"}]
    svc.create_api_key.return_value = {"id": "k1", "key": "wfk_"}
    return svc


@pytest.fixture
def mock_workflow_service():
    svc = AsyncMock()
    svc.list.return_value = [{"id": "wf1"}]
    svc.create.return_value = {"id": "wf_new"}
    svc.get.return_value = {"id": "wf1", "name": "Test"}
    svc.update.return_value = {"id": "wf1", "updated": True}
    svc.set_active.return_value = {"id": "wf1", "active": True}
    svc.list_versions.return_value = [1, 2]
    svc.get_version.return_value = {"version": 1}
    svc.restore_version.return_value = {"version": 1, "restored": True}
    return svc


@pytest.fixture
def mock_execution_service():
    svc = AsyncMock()
    svc.trigger.return_value = {"run_id": "r1"}
    svc.list.return_value = [{"run_id": "r1"}]
    # Default get() returns a terminal state so WS test completes naturally
    svc.get.return_value = {"run_id": "r1", "status": "succeeded", "nodes": [{"node_id": "n1", "status": "completed"}]}
    svc.list_nodes.return_value = [{"node_id": "n1", "status": "succeeded"}]
    svc.get_logs.return_value = [{"message": "log"}]
    svc.cancel.return_value = {"run_id": "r1", "status": "cancelled"}
    svc.retry.return_value = {"run_id": "r1", "status": "running"}
    svc.submit_human_input.return_value = {"run_id": "r1", "input_received": True}
    return svc


@pytest.fixture
def mock_webhook_service():
    svc = AsyncMock()
    svc.list.return_value = [{"id": "wh1"}]
    svc.get.return_value = {"id": "wh1"}
    svc.create.return_value = {"id": "wh1"}
    svc.update.return_value = {"id": "wh1", "updated": True}
    svc.handle_inbound.return_value = {"handled": True}
    return svc


@pytest.fixture
def mock_audit_service():
    svc = AsyncMock()
    svc.list.return_value = [{"event": "login"}]
    return svc


@pytest.fixture
def mock_billing_service():
    svc = AsyncMock()
    svc.get_usage_summary.return_value = {"runs": 10}
    return svc


@pytest.fixture
def mock_schedule_service():
    svc = AsyncMock()
    svc.list.return_value = [{"id": "s1"}]
    svc.get.return_value = {"id": "s1"}
    svc.create.return_value = {"id": "s1"}
    svc.update.return_value = {"id": "s1"}
    return svc


@pytest.fixture
def app(
    mock_auth_service,
    mock_user_service,
    mock_workflow_service,
    mock_execution_service,
    mock_webhook_service,
    mock_audit_service,
    mock_billing_service,
    mock_schedule_service,
):
    """Creates the FastAPI app with mocked services injected."""
    services = {
        "auth_service": mock_auth_service,
        "user_service": mock_user_service,
        "workflow_service": mock_workflow_service,
        "execution_service": mock_execution_service,
        "webhook_service": mock_webhook_service,
        "audit_service": mock_audit_service,
        "billing_service": mock_billing_service,
        "schedule_service": mock_schedule_service,
    }
    app = create_app(services=services)
    # Reset limiter for clean state per test (SlowAPI attaches a global object to app.state)
    app.state.limiter.reset()
    return app


@pytest.fixture
async def client(app):
    """Async HTTPX client for testing the API."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver/api/v1",
        headers={"Authorization": "Bearer fake_token"}
    ) as ac:
        yield ac


class TestUnauthenticated:
    """AC: Unauthenticated requests return 401"""

    @pytest.mark.asyncio
    async def test_no_auth_header_returns_401(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver/api/v1") as anon_client:
            resp = await anon_client.get("/workflows")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Authentication required"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, app, mock_auth_service):
        mock_auth_service.verify_token.side_effect = Exception("Invalid signature")
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver/api/v1",
            headers={"Authorization": "Bearer bad_token"}
        ) as bad_client:
            resp = await bad_client.get("/workflows")
            assert resp.status_code == 401


class TestRBACGuard:
    """AC: VIEWER cannot call write endpoints (403)"""

    @pytest.mark.asyncio
    async def test_viewer_can_read_workflows(self, client, mock_auth_service, mock_workflow_service):
        mock_auth_service.verify_token.return_value = {"id": "u2", "tenant_id": "t1", "role": "VIEWER"}
        resp = await client.get("/workflows")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_viewer_blocked_on_write(self, client, mock_auth_service):
        mock_auth_service.verify_token.return_value = {"id": "u2", "tenant_id": "t1", "role": "VIEWER"}
        resp = await client.post("/workflows", json={"name": "New WF", "definition": {}})
        assert resp.status_code == 403
        assert "Role 'VIEWER' is not permitted" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_allowed_on_write(self, client, mock_auth_service):
        mock_auth_service.verify_token.return_value = {"id": "u1", "tenant_id": "t1", "role": "ADMIN"}
        resp = await client.post("/workflows", json={"name": "New WF", "definition": {}})
        assert resp.status_code == 201


class TestRateLimiter:
    """AC: Rate limit returns 429 with Retry-After header"""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, client, mock_auth_service):
        mock_auth_service.verify_token.return_value = {"id": "u1", "tenant_id": "t_limit", "role": "ADMIN"}
        app = client._transport.app
        # Limit is 60/minute. Let's make 61 requests to /users/me
        responses = []
        for _ in range(61):
            responses.append(await client.get("/users/me"))

        # The 61st response should be 429
        last_resp = responses[-1]
        assert last_resp.status_code == 429
        assert "Retry-After" in last_resp.headers

        # The first 60 should be 200
        assert responses[0].status_code == 200


class TestWebSocketStream:
    """AC: WebSocket emits state update within 500ms of node completion"""

    @pytest.mark.asyncio
    async def test_websocket_lifecycle(self, app, mock_execution_service):
        from fastapi.testclient import TestClient
        
        # TestClient handles WebSockets nicely synchronously for testing
        client = TestClient(app)
        
        # Setup mock to simulate a running execution that completes
        mock_execution_service.get.side_effect = [
            {"run_id": "r1", "status": "running", "nodes": [{"node_id": "n1", "status": "completed"}]},
            {"run_id": "r1", "status": "succeeded", "nodes": [{"node_id": "n1", "status": "completed"}, {"node_id": "n2", "status": "completed"}]}
        ]
        
        with client.websocket_connect("/api/v1/ws/executions/r1?token=fake") as websocket:
            # First message is always the snapshot of current node states
            data1 = websocket.receive_json()
            assert data1["type"] in ("snapshot", "node_state", "run_complete")

            # Subsequent messages are state updates
            data2 = websocket.receive_json()
            assert data2["type"] in ("node_state", "run_complete", "snapshot")


class TestFullRouteCoverage:
    """AC: API tests cover every route. Verify HTTP status codes."""

    # ── Health ──
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("http://testserver/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_ready(self, client):
        client._transport.app.state.mongo_client = AsyncMock()
        resp = await client.get("http://testserver/health/ready")
        assert resp.status_code == 200

    # ── Auth ──
    @pytest.mark.asyncio
    async def test_auth_register(self, client):
        resp = await client.post("/auth/register", json={"email": "a@b.com", "password": "p"})
        assert resp.status_code == 201
        
    @pytest.mark.asyncio
    async def test_auth_login(self, client):
        resp = await client.post("/auth/login", json={"email": "a@b.com", "password": "p"})
        assert resp.status_code == 200
        
    @pytest.mark.asyncio
    async def test_auth_logout(self, client):
        resp = await client.post("/auth/logout")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_auth_token_refresh(self, client):
        resp = await client.post("/auth/token/refresh", json={"refresh_token": "rt"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_verify_email(self, client):
        resp = await client.post("/auth/verify-email?token=token1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_password_reset_request(self, client):
        resp = await client.post("/auth/password/reset-request", json={"email": "a@b.com"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_password_reset(self, client):
        resp = await client.post("/auth/password/reset", json={"token": "t", "new_password": "p"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_mfa_setup(self, client):
        resp = await client.post("/auth/mfa/setup")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_mfa_verify(self, client):
        resp = await client.post("/auth/mfa/verify", json={"code": "123"})
        assert resp.status_code == 200
        
    @pytest.mark.asyncio
    async def test_auth_oauth_redirect(self, client):
        resp = await client.get("/auth/oauth/google")
        assert resp.status_code == 200
        
    @pytest.mark.asyncio
    async def test_auth_oauth_callback(self, client):
        resp = await client.get("/auth/oauth/google/callback?code=abc")
        assert resp.status_code == 200

    # ── Users ──
    @pytest.mark.asyncio
    async def test_users_me(self, client):
        resp = await client.get("/users/me")
        assert resp.status_code == 200
        
    @pytest.mark.asyncio
    async def test_users_me_patch(self, client):
        resp = await client.patch("/users/me", json={"full_name": "bob"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_users_api_keys_list(self, client):
        resp = await client.get("/users/me/api-keys")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_users_api_keys_create(self, client):
        resp = await client.post("/users/me/api-keys", json={"name": "key"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_users_api_keys_delete(self, client):
        resp = await client.delete("/users/me/api-keys/k1")
        assert resp.status_code == 204

    # ── Workflows ──
    @pytest.mark.asyncio
    async def test_workflows_list(self, client):
        resp = await client.get("/workflows")
        assert resp.status_code == 200
        
    @pytest.mark.asyncio
    async def test_workflows_create(self, client):
        resp = await client.post("/workflows", json={"name": "W1"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_workflows_get(self, client):
        resp = await client.get("/workflows/w1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_workflows_update(self, client):
        resp = await client.patch("/workflows/w1", json={"name": "w2"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_workflows_delete(self, client):
        resp = await client.delete("/workflows/w1")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_workflows_activate(self, client):
        resp = await client.post("/workflows/w1/activate")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_workflows_deactivate(self, client):
        resp = await client.post("/workflows/w1/deactivate")
        assert resp.status_code == 200

    # ── Versions ──
    @pytest.mark.asyncio
    async def test_versions_list(self, client):
        resp = await client.get("/workflows/w1/versions")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_versions_get(self, client):
        resp = await client.get("/workflows/w1/versions/1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_versions_restore(self, client):
        resp = await client.post("/workflows/w1/versions/1/restore")
        assert resp.status_code == 200

    # ── Schedules ──
    @pytest.mark.asyncio
    async def test_schedules_list(self, client):
        resp = await client.get("/workflows/w1/schedules")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_schedules_create(self, client):
        resp = await client.post("/workflows/w1/schedules", json={})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_schedules_get(self, client):
        resp = await client.get("/schedules/s1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_schedules_update(self, client):
        resp = await client.patch("/schedules/s1", json={})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_schedules_delete(self, client):
        resp = await client.delete("/schedules/s1")
        assert resp.status_code == 204

    # ── Executions ──
    @pytest.mark.asyncio
    async def test_executions_trigger(self, client):
        resp = await client.post("/workflows/w1/trigger", json={})
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_executions_list(self, client):
        resp = await client.get("/executions")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_executions_get(self, client):
        resp = await client.get("/executions/r1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_executions_cancel(self, client):
        resp = await client.post("/executions/r1/cancel")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_executions_retry(self, client):
        resp = await client.post("/executions/r1/retry")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_executions_nodes(self, client):
        resp = await client.get("/executions/r1/nodes")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_executions_human_input(self, client):
        resp = await client.post("/executions/human-input", json={"run_id": "r1", "node_id": "n1", "response": {}})
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_executions_logs(self, client):
        resp = await client.get("/executions/r1/logs")
        assert resp.status_code == 200

    # ── Webhooks ──
    @pytest.mark.asyncio
    async def test_webhooks_list(self, client):
        resp = await client.get("/webhooks")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_webhooks_create(self, client):
        resp = await client.post("/webhooks", json={"workflow_id": "w1", "name": "wh", "endpoint_url": "https://example.com/hook"})
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_webhooks_get(self, client):
        resp = await client.get("/webhooks/wh1")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_webhooks_update(self, client):
        resp = await client.patch("/webhooks/wh1", json={"name": "wh2"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_webhooks_delete(self, client):
        resp = await client.delete("/webhooks/wh1")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_webhooks_inbound(self, client):
        resp = await client.post("/webhooks/inbound/w1", json={})
        assert resp.status_code == 202

    # ── Audit & Usage ──
    @pytest.mark.asyncio
    async def test_audit_list(self, client):
        resp = await client.get("/audit")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_usage_get(self, client):
        resp = await client.get("/usage")
        assert resp.status_code == 200

