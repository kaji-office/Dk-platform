"""
APIKeyService — platform API key lifecycle management.

Key format: wfk_{random_hex_40}
  - Prefix "wfk_" makes keys recognizable and scannable in logs/git.
  - 40 hex chars = 160 bits of entropy (cryptographically strong).
  - Only the SHA-256 hash is stored in the database.
  - The first 12 characters (prefix + 8 chars) are stored for display
    so users can identify keys without exposing the secret.

Scopes (fine-grained permissions):
  - "workflows:read"       — list + get workflow definitions
  - "workflows:write"      — create + update + delete workflows
  - "executions:trigger"   — trigger workflow runs
  - "executions:read"      — view run history and logs
  - "admin"               — full tenant admin access
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Sequence

from workflow_engine.auth.models import APIKeyRecord
from workflow_engine.errors import AuthenticationError, InsufficientPermissionsError

_KEY_PREFIX = "wfk_"
_KEY_ENTROPY_BYTES = 20   # 40 hex chars

VALID_SCOPES = frozenset({
    "workflows:read",
    "workflows:write",
    "executions:trigger",
    "executions:read",
    "schedules:read",
    "schedules:write",
    "admin",
})


class APIKeyService:
    """
    Manages API key creation, verification, and revocation.

    This service is stateless — it does NOT persist anything itself.
    Callers must save/load APIKeyRecord objects through their own repository.
    """

    @staticmethod
    def create(
        tenant_id: str,
        name: str,
        scopes: list[str],
    ) -> tuple[str, APIKeyRecord]:
        """
        Generate a new API key.

        The raw key is returned ONCE — the caller must display it to the user
        immediately and store only the hash.

        Args:
            tenant_id: Owning tenant.
            name: Human-readable label (e.g. "CI/CD Pipeline key").
            scopes: List of permission scopes.

        Returns:
            (raw_key, APIKeyRecord) — raw_key shown once, record persisted.

        Raises:
            ValueError: If any scope is invalid.
        """
        invalid = set(scopes) - VALID_SCOPES
        if invalid:
            raise ValueError(f"Invalid scopes: {invalid}. Valid scopes: {VALID_SCOPES}")

        raw_key = _KEY_PREFIX + secrets.token_hex(_KEY_ENTROPY_BYTES)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        prefix = raw_key[:12]  # "wfk_" + first 8 chars

        record = APIKeyRecord(
            key_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            scopes=scopes,
            created_at=datetime.now(tz=timezone.utc),
        )
        return raw_key, record

    @staticmethod
    def verify(raw_key: str, stored_records: Sequence[APIKeyRecord]) -> APIKeyRecord | None:
        """
        Verify a submitted API key against a list of stored records.

        Args:
            raw_key: The raw key string submitted in the request header.
            stored_records: All APIKeyRecord objects for the tenant.

        Returns:
            The matching APIKeyRecord if valid and not revoked, else None.
        """
        if not raw_key.startswith(_KEY_PREFIX):
            return None

        submitted_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        now = datetime.now(tz=timezone.utc)

        for record in stored_records:
            if record.revoked:
                continue
            if record.expires_at and record.expires_at < now:
                continue
            if record.key_hash == submitted_hash:
                return record

        return None

    @staticmethod
    def check_scope(record: APIKeyRecord, required_scope: str) -> None:
        """
        Assert that an API key has the required scope.

        Raises:
            InsufficientPermissionsError: If the key lacks the scope.
        """
        if "admin" in record.scopes:
            return  # admin keys have all permissions
        if required_scope not in record.scopes:
            raise InsufficientPermissionsError(
                f"API key '{record.prefix}...' does not have scope '{required_scope}'."
            )

    @staticmethod
    def revoke(record: APIKeyRecord) -> APIKeyRecord:
        """
        Return a revoked copy of an APIKeyRecord.
        Caller must persist the returned record.
        """
        from dataclasses import replace
        return replace(record, revoked=True)
