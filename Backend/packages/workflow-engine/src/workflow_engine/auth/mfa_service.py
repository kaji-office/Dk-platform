"""
MFAService — TOTP-based MFA using pyotp + single-use backup codes.

Security notes:
  - TOTP secret is returned in plain text only at setup time (MFASetup).
    The caller MUST encrypt it before storing (e.g. AES-256-GCM via KMS).
  - Backup codes are SHA-256 hashed before storage. Plain codes shown once.
  - verify_backup_code is NOT idempotent — it consumes the code on success.
    Caller must persist the updated BackupCode list.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

import pyotp

from workflow_engine.auth.models import BackupCode, MFASetup

_BACKUP_CODE_COUNT = 8
_BACKUP_CODE_LENGTH = 10  # characters


class MFAService:
    """
    Manages TOTP-based multi-factor authentication and backup codes.

    All persistence is delegated to the caller — this service is stateless.
    """

    @staticmethod
    def setup(user_id: str) -> MFASetup:
        """
        Generate a new TOTP secret + 8 backup codes for a user.

        The caller MUST:
          1. Encrypt and store the returned secret.
          2. Hash and store the backup_codes (as BackupCode records).
          3. Show the plain backup_codes to the user exactly once.

        Returns:
            MFASetup with secret, provisioning URI (for QR), and plain backup codes.
        """
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=user_id, issuer_name="DK Platform")
        plain_backup_codes = [
            secrets.token_hex(_BACKUP_CODE_LENGTH // 2)
            for _ in range(_BACKUP_CODE_COUNT)
        ]
        return MFASetup(
            secret=secret,
            provisioning_uri=uri,
            backup_codes=plain_backup_codes,
        )

    @staticmethod
    def hash_backup_codes(plain_codes: list[str]) -> list[BackupCode]:
        """
        Hash plain backup codes into BackupCode records for storage.

        Args:
            plain_codes: List of raw plain-text codes from setup().

        Returns:
            List of BackupCode dataclasses ready to be persisted.
        """
        return [
            BackupCode(code_hash=hashlib.sha256(code.encode()).hexdigest())
            for code in plain_codes
        ]

    @staticmethod
    def verify(secret: str, code: str) -> bool:
        """
        Verify a 6-digit TOTP code against the user's stored secret.

        Uses a ±1 window (30s tolerance for clock drift).

        Args:
            secret: Decrypted base32 TOTP secret from storage.
            code: 6-digit code submitted by user.

        Returns:
            True if valid, False otherwise.
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)

    @staticmethod
    def verify_backup_code(
        submitted: str,
        stored_codes: list[BackupCode],
    ) -> tuple[bool, list[BackupCode]]:
        """
        Verify a backup code and mark it as consumed.

        Args:
            submitted: Plain-text backup code entered by the user.
            stored_codes: Current list of BackupCode records from DB.

        Returns:
            (success: bool, updated_codes: list[BackupCode])
            The caller MUST save the updated_codes back to the database.
        """
        code_hash = hashlib.sha256(submitted.encode()).hexdigest()
        updated: list[BackupCode] = []
        found = False

        for bc in stored_codes:
            if bc.code_hash == code_hash and not bc.used:
                updated.append(
                    BackupCode(
                        code_hash=bc.code_hash,
                        used=True,
                        used_at=datetime.now(tz=timezone.utc),
                    )
                )
                found = True
            else:
                updated.append(bc)

        return found, updated

    @staticmethod
    def remaining_backup_codes(stored_codes: list[BackupCode]) -> int:
        """Return how many unused backup codes remain."""
        return sum(1 for bc in stored_codes if not bc.used)
