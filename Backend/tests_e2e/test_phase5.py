import asyncio
import httpx
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# 1. API 
from workflow_api.app import create_app
from fastapi.testclient import TestClient

# 2. Celery Worker (E-2)
from workflow_worker.celery_app import app as celery_app
from workflow_worker.tasks import execute_workflow

# 3. CLI (E-3)
from workflow_cli.cli import cli
from click.testing import CliRunner

# Configuration
celery_app.conf.task_always_eager = False

class MockAuthService:
    async def verify_token(self, token):
        if token == "mockjwt123":
            return {"sub": "user1", "tenant_id": "tenant1", "role": "ADMIN"}
        raise Exception("Invalid")

class MockWfService:
    async def list_workflows(self, tenant_id):
        return [{"id": "wf-1", "name": "Test WF"}]
    async def get_workflow(self, wf_id, tenant_id):
        return {"id": "wf-1"}

class MockExecService:
    async def trigger(self, wf_id, payload, tenant):
        return {"id": "run-123", "status": "QUEUED"}

class TestPhase5EndToEnd:

    @pytest.fixture
    def api_client(self):
        auth_svc = MockAuthService()
        mock_wf_svc = MockWfService()
        mock_exec_svc = MockExecService()
        
        app = create_app(services={
            "auth_service": auth_svc,
            "workflow_service": mock_wf_svc,
            "execution_service": mock_exec_svc
        })
        
        return TestClient(app)

    @pytest.fixture
    def cli_runner(self):
        return CliRunner()

    def test_full_phase5_integration(self, api_client, cli_runner, monkeypatch):
        """End-to-End simulation of E-3 (CLI) -> E-1 (API) -> E-2 (Worker)"""
        
        # 1. Patch the CLI's internally used httpx requests to point to our TestClient
        def mock_request(method, url, **kwargs):
            # Map absolute URLs to relative for TestClient
            path = url.replace("http://127.0.0.1:8000", "")
            print(f"DEBUG Headers sent for {path}: {kwargs.get('headers')}")
            if method == "POST":
                return api_client.post(path, json=kwargs.get("json"), headers=kwargs.get("headers"))
            elif method == "GET":
                return api_client.get(path, headers=kwargs.get("headers"))
            elif method == "DELETE":
                return api_client.delete(path, headers=kwargs.get("headers"))
            
        monkeypatch.setattr("workflow_cli.commands.workflow._request", mock_request)
        monkeypatch.setattr("workflow_cli.commands.run._request", mock_request)
        
        # 2. Simulate User Login (CLI -> API)
        def mock_auth_request(url, **kwargs):
            # Simulate a successful token grab
            res = MagicMock()
            res.is_success = True
            res.json.return_value = {"access_token": "mockjwt123"}
            return res
        import tempfile
        from pathlib import Path
        tmp_config = Path(tempfile.mktemp())
        tmp_config.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("workflow_cli.commands.auth.httpx.post", mock_auth_request)
        monkeypatch.setattr("workflow_cli.config.CONFIG_FILE", tmp_config)
        
        login_result = cli_runner.invoke(cli, ["auth", "login"], input="admin@test.com\npassword\n")
        assert login_result.exit_code == 0, f"Login failed: {login_result.output}"
        assert "Successfully logged in!" in login_result.output

        # 3. CLI -> API Workflow List
        list_result = cli_runner.invoke(cli, ["workflow", "list"])
        assert list_result.exit_code == 0
        assert "Test WF" in list_result.output

        # 4. CLI -> API Trigger Workflow -> (Would trigger E-2 queue)
        trigger_result = cli_runner.invoke(cli, ["run", "trigger", "wf-1"])
        assert trigger_result.exit_code == 0
        assert "run-123" in trigger_result.output
