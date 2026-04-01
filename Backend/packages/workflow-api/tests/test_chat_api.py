import pytest
from fastapi.testclient import TestClient
from workflow_api.app import app
import builtins

@pytest.fixture
def mock_app_state(monkeypatch):
    """Mocks dependencies inside app.state so the tests can execute safely."""
    # Since we aren't initializing real Mongo in this unit test block,
    # we mock the chat_orchestrator at the FastAPI dependency level or app.state.
    class MockOrchestrator:
        async def create_session(self, tenant_id, user_id):
            return {"session_id": "sess-123", "phase": "GATHERING"}
            
        async def get_session(self, session_id, tenant_id):
            return {"session_id": "sess-123", "phase": "GATHERING"}
            
        async def list_sessions(self, tenant_id):
            return [{"session_id": "sess-123", "phase": "GATHERING"}]
            
        async def process_message(self, session_id, tenant_id, content):
            from workflow_engine.chat.models import ConversationPhase
            return {"message": "Mock Response", "phase": ConversationPhase.CLARIFYING, "clarification": None, "requirement_spec": None, "workflow_preview": None, "workflow_id": None}
            
        async def generate_workflow(self, session_id, tenant_id):
            return {"workflow_id": "wf-123", "workflow_preview": {"nodes": {}, "edges": []}}

        async def validate_workflow_update(self, session_id, tenant_id, update):
            return {"valid": True, "workflow": {}, "suggestions": []}

    app.state.chat_orchestrator = MockOrchestrator()
    return app

@pytest.fixture
def override_auth():
    from workflow_api.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"sub": "user-1", "tenant_id": "tenant-1", "role": "EDITOR"}
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def client(mock_app_state, override_auth):
    return TestClient(app)

def test_create_session(client):
    response = client.post("/v1/chat/sessions")
    assert response.status_code == 201
    assert "session_id" in response.json()

def test_get_session(client):
    response = client.get("/v1/chat/sessions/sess-123")
    assert response.status_code == 200

def test_list_sessions(client):
    response = client.get("/v1/chat/sessions")
    assert response.status_code == 200

def test_post_message(client):
    response = client.post("/v1/chat/sessions/sess-123/message", json={"content": "Hello"})
    assert response.status_code == 200
    assert response.json()["message"] == "Mock Response"

def test_force_generate(client):
    response = client.post("/v1/chat/sessions/sess-123/generate")
    assert response.status_code == 200
    assert response.json()["workflow_id"] == "wf-123"

def test_workflow_edit(client):
    response = client.put("/v1/chat/sessions/sess-123/workflow", json={"nodes": {}, "edges": [], "ui_metadata": {}})
    assert response.status_code == 200
    assert response.json()["valid"] is True

def test_websocket_endpoint(client):
    with client.websocket_connect("/ws/chat/sess-123") as websocket:
        data = websocket.receive_json()
        assert data == {"type": "connected", "session_id": "sess-123"}
