import logging
import json
import io
from pytest import CaptureFixture

from workflow_engine.observability.logging import configure_structured_logging, get_logger

def test_json_structured_logging(capsys: CaptureFixture):
    configure_structured_logging(level=logging.INFO)
    logger = get_logger("test.module")
    
    logger.info("Executing a test task", extra={"tenant_id": "test_tenant"})
    
    # We can capture sys.stdout which JSON logger dumps into
    captured = capsys.readouterr()
    stdout_lines = [l for l in captured.out.split("\n") if l.strip()]
    
    # Check that output is parsed JSON
    assert len(stdout_lines) >= 1
    log_data = json.loads(stdout_lines[-1])
    
    # Ensure fields like "message", "level", "name" are standard keys
    assert "message" in log_data
    assert log_data["message"] == "Executing a test task"
    assert "level" in log_data
    assert log_data["level"] == "INFO"
    assert "name" in log_data
    assert log_data["name"] == "test.module"
    
    # In python-json-logger, extra arguments get automatically appended
    assert "tenant_id" in log_data
    assert log_data["tenant_id"] == "test_tenant"
