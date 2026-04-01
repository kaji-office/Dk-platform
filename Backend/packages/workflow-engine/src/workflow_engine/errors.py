from typing import Any


class WorkflowEngineError(Exception):
    """Base exception for all workflow engine errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message
        }

class WorkflowNotFoundError(WorkflowEngineError):
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow not found: {workflow_id}", code="WORKFLOW_NOT_FOUND")

class WorkflowValidationError(WorkflowEngineError):
    def __init__(self, message: str):
        super().__init__(message, code="WORKFLOW_VALIDATION_ERROR")

class ExecutionError(WorkflowEngineError):
    def __init__(self, message: str, code: str = "EXECUTION_ERROR"):
        super().__init__(message, code=code)

class NodeExecutionError(ExecutionError):
    def __init__(self, node_id: str, message: str):
        super().__init__(f"Node {node_id} failed: {message}", code="NODE_EXECUTION_ERROR")
        self.node_id = node_id

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["node_id"] = self.node_id
        return d

class SandboxTimeoutError(ExecutionError):
    def __init__(self, message: str = "Sandbox execution timed out"):
        super().__init__(message, code="SANDBOX_TIMEOUT")

class SandboxMemoryError(ExecutionError):
    def __init__(self, message: str = "Sandbox memory limit exceeded"):
        super().__init__(message, code="SANDBOX_MEMORY_EXCEEDED")

class QuotaExceededError(WorkflowEngineError):
    def __init__(self, message: str):
        super().__init__(message, code="QUOTA_EXCEEDED")

class TenantNotFoundError(WorkflowEngineError):
    def __init__(self, tenant_id: str):
        super().__init__(f"Tenant not found: {tenant_id}", code="TENANT_NOT_FOUND")

class AuthError(WorkflowEngineError):
    def __init__(self, message: str, code: str = "UNAUTHORIZED"):
        super().__init__(message, code=code)

class AuthenticationError(AuthError):
    """Raised when identity verification fails (wrong password, bad OAuth code, etc.)."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="AUTHENTICATION_FAILED")

class TokenExpiredError(AuthError):
    def __init__(self, message: str = "Token has expired"):
        super().__init__(message, code="TOKEN_EXPIRED")

class InvalidTokenError(AuthError):
    """Raised when a token is malformed, has wrong type, or fails signature verification."""
    def __init__(self, message: str = "Invalid token"):
        super().__init__(message, code="INVALID_TOKEN")

class InsufficientPermissionsError(AuthError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, code="FORBIDDEN")

class PIIBlockedError(WorkflowEngineError):
    def __init__(self, message: str = "PII detected and blocked by policy"):
        super().__init__(message, code="PII_BLOCKED")

class FeatureDisabledError(WorkflowEngineError):
    def __init__(self, message: str = "Feature is not enabled"):
        super().__init__(message, code="FEATURE_DISABLED")

class ConnectorError(WorkflowEngineError):
    def __init__(self, connector_name: str, message: str):
        super().__init__(f"Connector {connector_name} error: {message}", code="CONNECTOR_ERROR")
        self.connector_name = connector_name

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["connector_name"] = self.connector_name
        return d
