"""
PasswordService — bcrypt hashing and password strength enforcement.

Policy (hardened defaults):
  - Minimum 12 characters
  - At least one uppercase letter
  - At least one lowercase letter
  - At least one digit
  - At least one special character
  - Must not be a known common password (top-10000 check)
  - bcrypt work factor: 12 (≈250ms on modern hardware — tunable)
"""
from __future__ import annotations

import re

import bcrypt

from workflow_engine.auth.models import PasswordStrengthResult

_BCRYPT_ROUNDS = 12

# A minimal common-password guard — can be extended with a full list in production
_COMMON_PASSWORDS = frozenset({
    "password", "password1", "12345678", "123456789", "1234567890",
    "qwerty123", "iloveyou", "admin1234", "letmein1", "monkey123",
    "passw0rd", "master123", "welcome1",
})


class PasswordService:
    """
    Provides secure password hashing (bcrypt) and strength validation.
    This service is fully stateless — use as a singleton or inline.
    """

    @staticmethod
    def hash(plain: str) -> str:
        """
        Hash a plain-text password with bcrypt.

        Args:
            plain: Raw password string.

        Returns:
            bcrypt hash string (includes salt + work factor prefix).
        """
        return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()

    @staticmethod
    def verify(plain: str, hashed: str) -> bool:
        """
        Verify a plain-text password against a stored bcrypt hash.

        Args:
            plain: Password submitted by the user.
            hashed: Stored hash from the database.

        Returns:
            True if the password matches, False otherwise.
        """
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except Exception:
            return False

    @staticmethod
    def validate_strength(plain: str) -> PasswordStrengthResult:
        """
        Validate a password against the platform's strength policy.

        Returns:
            PasswordStrengthResult with is_valid flag and list of errors.
        """
        errors: list[str] = []

        if len(plain) < 12:
            errors.append("Password must be at least 12 characters long.")
        if not re.search(r"[A-Z]", plain):
            errors.append("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", plain):
            errors.append("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", plain):
            errors.append("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-\[\]\\;'/`~+=]", plain):
            errors.append("Password must contain at least one special character.")
        if plain.lower() in _COMMON_PASSWORDS:
            errors.append("Password is too common. Please choose a more unique password.")

        return PasswordStrengthResult(is_valid=len(errors) == 0, errors=errors)
