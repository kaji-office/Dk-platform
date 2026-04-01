"""
Auth module — domain models for D-1.
TokenClaims, OAuthProfile, APIKeyRecord, BackupCode, MFASetup.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Role(str, Enum):
    """RBAC roles — ordered by privilege level (higher value = more privilege)."""
    VIEWER     = "VIEWER"
    EDITOR     = "EDITOR"
    OWNER      = "OWNER"
    SUPERADMIN = "SUPERADMIN"

    def __ge__(self, other: "Role") -> bool:
        _order = list(Role)
        return _order.index(self) >= _order.index(other)

    def __gt__(self, other: "Role") -> bool:
        _order = list(Role)
        return _order.index(self) > _order.index(other)


@dataclass
class TokenClaims:
    """Decoded claims from a verified JWT."""
    user_id: str
    tenant_id: str
    roles: list[Role]
    token_type: str            # "access" | "refresh"
    exp: datetime
    jti: str                   # unique token ID for revocation


@dataclass
class OAuthCredentials:
    """OAuth2 app credentials for a provider (injected at setup time)."""
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass
class OAuthProfile:
    """Normalised user profile returned by any OAuth2 provider."""
    provider: str              # "google" | "github" | "microsoft"
    provider_user_id: str
    email: str
    display_name: str
    avatar_url: str | None = None
    raw_profile: dict[str, Any] = field(default_factory=dict)


@dataclass
class APIKeyRecord:
    """Stored API key record (never stores raw key, only hash)."""
    key_id: str
    tenant_id: str
    name: str
    key_hash: str              # SHA-256 of raw key
    prefix: str                # first 8 chars e.g. "wfk_a1b2"
    scopes: list[str]          # e.g. ["workflows:read", "executions:trigger"]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked: bool = False
    expires_at: datetime | None = None


@dataclass
class BackupCode:
    """Single-use MFA backup code record."""
    code_hash: str         # SHA-256 of the raw code (never stored plain)
    used: bool = False
    used_at: datetime | None = None


@dataclass
class MFASetup:
    """Returned when MFA TOTP is first configured."""
    secret: str                   # base32 TOTP secret
    provisioning_uri: str         # otpauth:// URI for QR code
    backup_codes: list[str]       # 8 plain-text codes (shown once)


@dataclass
class PasswordStrengthResult:
    """Result from PasswordService.validate_strength()."""
    is_valid: bool
    errors: list[str]
