"""
Tests for DK Workflow CLI

Validates:
- `wf run trigger <workflow_id>` exits 0 on QUEUED, 1 on error
- `wf run logs <run_id> --follow` streams logs to stdout
- Config stored in `~/.config/wf/config.toml`
"""
from click.testing import CliRunner
from workflow_cli.cli import cli
from unittest.mock import patch, MagicMock
from workflow_cli.config import CONFIG_FILE

def test_config_path_ac():
    """AC: Config stored in ~/.config/wf/config.toml"""
    assert str(CONFIG_FILE).endswith(".config/wf/config.toml")

@patch("workflow_cli.commands.run._request")
def test_run_trigger_success_exit_0(mock_req):
    """AC: wf run trigger <workflow_id> exits 0 on QUEUED"""
    mock_res = MagicMock()
    mock_res.is_success = True
    mock_res.json.return_value = {"data": {"id": "run-1", "status": "QUEUED"}}
    mock_req.return_value = mock_res
    
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "trigger", "wf-1", "--input-data", '{"test": 1}'])
    
    assert result.exit_code == 0
    assert "QUEUED run:" in result.output

@patch("workflow_cli.commands.run._request")
def test_run_trigger_error_exit_1(mock_req):
    """AC: wf run trigger <workflow_id> exits 1 on error"""
    mock_res = MagicMock()
    mock_res.is_success = False
    mock_res.text = "Internal Server Error"
    mock_req.return_value = mock_res
    
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "trigger", "wf-1"])
    
    assert result.exit_code == 1
    assert "Error triggering run" in result.output

@patch("workflow_cli.commands.run.websockets.connect")
@patch("workflow_cli.commands.run.get_token")
def test_run_logs_follow(mock_get_token, mock_ws_connect):
    """AC: wf run logs <run_id> --follow streams logs to stdout"""
    mock_get_token.return_value = "token"
    
    # Mock async context manager for websockets
    mock_ws = MagicMock()
    mock_ws.__aenter__.return_value = mock_ws
    
    # We yield two messages then raise exception to close stream smoothly in test
    import json
    msg1 = json.dumps({"type": "node_update", "node_id": "A", "status": "RUNNING"})
    msg2 = json.dumps({"type": "terminal", "status": "SUCCESS"})
    mock_ws.recv = MagicMock()
    
    # Need to simulate the async behavior natively
    class AsyncMockWithRecv:
        def __init__(self):
            self.calls = 0
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
        async def recv(self):
            if self.calls == 0:
                self.calls += 1
                return msg1
            if self.calls == 1:
                self.calls += 1
                return msg2
            raise Exception("Stop async iteration")
            
    mock_ws_connect.return_value = AsyncMockWithRecv()
    
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "logs", "run-1", "--follow"])
    
    assert result.exit_code == 0
    assert "RUNNING" in result.output
    assert "Execution terminated: SUCCESS" in result.output
