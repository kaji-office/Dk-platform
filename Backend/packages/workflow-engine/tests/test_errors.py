from workflow_engine.errors import (
    ConnectorError,
    NodeExecutionError,
    WorkflowEngineError,
    WorkflowNotFoundError,
    WorkflowValidationError,
    SandboxTimeoutError,
    SandboxMemoryError,
    QuotaExceededError,
    TenantNotFoundError,
    TokenExpiredError,
    InsufficientPermissionsError,
    PIIBlockedError,
)


def test_base_error_to_dict():
    err = WorkflowEngineError("A generic error")
    d = err.to_dict()
    assert d["code"] == "INTERNAL_ERROR"
    assert d["message"] == "A generic error"

def test_workflow_not_found_error():
    err = WorkflowNotFoundError("wf-1")
    d = err.to_dict()
    assert d["code"] == "WORKFLOW_NOT_FOUND"
    assert "wf-1" in d["message"]

def test_node_execution_error():
    err = NodeExecutionError("node-1", "Failed to parse JSON")
    d = err.to_dict()
    assert d["code"] == "NODE_EXECUTION_ERROR"
    assert d["node_id"] == "node-1"
    assert "Failed to parse JSON" in d["message"]

def test_connector_error():
    err = ConnectorError("Slack", "Timeout")
    d = err.to_dict()
    assert d["code"] == "CONNECTOR_ERROR"
    assert d["connector_name"] == "Slack"
    assert "Timeout" in d["message"]

def test_other_errors():
    assert WorkflowValidationError("").code == "WORKFLOW_VALIDATION_ERROR"
    assert SandboxTimeoutError().code == "SANDBOX_TIMEOUT"
    assert SandboxMemoryError().code == "SANDBOX_MEMORY_EXCEEDED"
    assert QuotaExceededError("").code == "QUOTA_EXCEEDED"
    assert TenantNotFoundError("t1").code == "TENANT_NOT_FOUND"
    assert TokenExpiredError().code == "TOKEN_EXPIRED"
    assert InsufficientPermissionsError().code == "FORBIDDEN"
    assert PIIBlockedError().code == "PII_BLOCKED"
