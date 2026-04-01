"""Auth module public API."""
from workflow_engine.auth.models import (
    Role,
    TokenClaims,
    OAuthProfile,
    OAuthCredentials,
    APIKeyRecord,
    BackupCode,
    MFASetup,
    PasswordStrengthResult,
)
from workflow_engine.auth.jwt_service import JWTService
from workflow_engine.auth.oauth_service import OAuthService
from workflow_engine.auth.mfa_service import MFAService
from workflow_engine.auth.password_service import PasswordService
from workflow_engine.auth.api_key_service import APIKeyService, VALID_SCOPES
from workflow_engine.auth.rbac import RBACGuard, require_role

__all__ = [
    "Role",
    "TokenClaims",
    "OAuthProfile",
    "OAuthCredentials",
    "APIKeyRecord",
    "BackupCode",
    "MFASetup",
    "PasswordStrengthResult",
    "JWTService",
    "OAuthService",
    "MFAService",
    "PasswordService",
    "APIKeyService",
    "VALID_SCOPES",
    "RBACGuard",
    "require_role",
]
