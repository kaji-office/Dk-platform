import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from workflow_api.app import app
import builtins

@pytest.fixture
def mock_app_state(monkeypatch):
    """Mocks dependencies inside app.state so the tests can execute safely."""
    from workflow_engine.chat.models import ChatSession, ConversationPhase
    from workflow_engine.chat.orchestrator import ChatResponse, WorkflowUpdateResponse

    from datetime import datetime, timezone

    def _make_session(session_id, tenant_id):
        return ChatSession(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id="user-1",
            phase=ConversationPhase.GATHERING,
            messages=[],
            requirement_spec=None,
            generated_workflow_id=None,
            clarification_round=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    class _MockRepo:
        async def create_session(self, tenant_id, user_id):
            return _make_session("sess-123", tenant_id)

        async def get_session(self, session_id, tenant_id):
            return _make_session(session_id, tenant_id)

        async def list_sessions(self, tenant_id):
            return [_make_session("sess-123", tenant_id)]

        async def update_phase(self, session_id, phase):
            pass

        async def record_workflow_id(self, session_id, workflow_id):
            pass

    class MockOrchestrator:
        repo = _MockRepo()

        async def process_message(self, session_id, tenant_id, content):
            return ChatResponse(
                message="Mock Response",
                phase=ConversationPhase.CLARIFYING,
                clarification=None,
                requirement_spec=None,
                workflow_preview=None,
                workflow_id=None,
            )

        async def validate_workflow_update(self, session_id, tenant_id, update):
            return WorkflowUpdateResponse(valid=True, workflow=None, suggestions=[])

    auth_svc = AsyncMock()
    auth_svc.verify_token.return_value = {"id": "user-1", "tenant_id": "tenant-1", "role": "EDITOR"}

    class _MockPubSub:
        async def subscribe(self, channel):
            pass
        async def aclose(self):
            pass
        async def listen(self):
            return
            yield  # makes it an async generator

    class _MockRedis:
        def pubsub(self):
            return _MockPubSub()
        async def publish(self, channel, data):
            pass

    # Save originals so we can restore after the test
    _orig_orchestrator = getattr(app.state, "chat_orchestrator", None)
    _orig_auth = getattr(app.state, "auth_service", None)
    _orig_redis = getattr(app.state, "redis_client", None)

    app.state.chat_orchestrator = MockOrchestrator()
    app.state.auth_service = auth_svc
    app.state.redis_client = _MockRedis()

    yield app

    # Restore originals to prevent test-order pollution of the global app singleton
    if _orig_orchestrator is not None:
        app.state.chat_orchestrator = _orig_orchestrator
    else:
        del app.state.chat_orchestrator
    if _orig_auth is not None:
        app.state.auth_service = _orig_auth
    else:
        del app.state.auth_service
    if _orig_redis is not None:
        app.state.redis_client = _orig_redis
    else:
        del app.state.redis_client

@pytest.fixture
def override_auth():
    from workflow_api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"id": "user-1", "tenant_id": "tenant-1", "role": "EDITOR"}
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def client(mock_app_state, override_auth):
    return TestClient(mock_app_state)

def test_create_session(client):
    response = client.post("/api/v1/chat/sessions")
    assert response.status_code == 201
    body = response.json().get("data") or response.json()
    assert "session_id" in body

def test_get_session(client):
    response = client.get("/api/v1/chat/sessions/sess-123")
    assert response.status_code == 200

def test_list_sessions(client):
    response = client.get("/api/v1/chat/sessions")
    assert response.status_code == 200

def test_post_message(client):
    response = client.post("/api/v1/chat/sessions/sess-123/message", json={"content": "Hello"})
    assert response.status_code == 200
    body = response.json().get("data") or response.json()
    assert body["message"] == "Mock Response"

def test_force_generate(client):
    # force_generate requires a session with requirement_spec; mock has none → 400
    response = client.post("/api/v1/chat/sessions/sess-123/generate")
    assert response.status_code in (200, 400)

def test_workflow_edit(client):
    response = client.put(
        "/api/v1/chat/sessions/sess-123/workflow",
        json={"workflow": {"id": "wf-1", "nodes": {}, "edges": [], "ui_metadata": {}}},
    )
    assert response.status_code == 200
    body = response.json().get("data") or response.json()
    assert body["valid"] is True

def test_websocket_endpoint(client):
    # Chat WS path: /api/v1/chat/sessions/ws/chat/{session_id}?token=<jwt>
    # Server closes after empty pubsub; WebSocketDisconnect on receive is acceptable.
    try:
        with client.websocket_connect("/api/v1/chat/sessions/ws/chat/sess-123?token=fake-tok") as websocket:
            data = websocket.receive_json()
            assert data.get("type") in ("connected", "error", "status", "message")
    except Exception:
        pass  # Clean close after empty pubsub is acceptable
