"""
JWTService — RS256 access tokens (15 min) + HS256 refresh tokens (7 days).

Design decisions:
  - Access tokens: RS256 (asymmetric) — public key can be distributed to
    downstream services for local verification without shared secrets.
  - Refresh tokens: HS256 (symmetric) — only the auth service needs to verify,
    no need for asymmetric overhead.
  - JTI (JWT ID) embedded in every token for revocation support.
  - All error cases raise typed errors from workflow_engine.errors.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import jwt

from workflow_engine.auth.models import Role, TokenClaims
from workflow_engine.errors import (
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError,
)

_ACCESS_TTL_MINUTES = 15
_REFRESH_TTL_DAYS = 7


class JWTService:
    """
    Issues and verifies JWTs for the DK Platform.

    Args:
        private_key: PEM-encoded RSA private key (for signing access tokens).
        public_key:  PEM-encoded RSA public key (for verifying access tokens).
        refresh_secret: HMAC secret string (for refresh tokens).
        issuer: Token issuer claim (default "dk-platform").
        audience: Token audience claim (default "dk-platform-api").
    """

    def __init__(
        self,
        private_key: str,
        public_key: str,
        refresh_secret: str,
        issuer: str = "dk-platform",
        audience: str = "dk-platform-api",
    ) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._refresh_secret = refresh_secret
        self._issuer = issuer
        self._audience = audience

    # ── Access token ──────────────────────────────────────────────────────────

    def issue_access_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[Role],
    ) -> str:
        """Issue a short-lived RS256 access token (15 min)."""
        now = datetime.now(tz=timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "tid": tenant_id,
            "roles": [r.value for r in roles],
            "type": "access",
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + timedelta(minutes=_ACCESS_TTL_MINUTES),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_access_token(self, token: str) -> TokenClaims:
        """Verify RS256 access token and return decoded claims."""
        return self._decode(token, self._public_key, algorithm="RS256", expected_type="access")

    # ── Refresh token ─────────────────────────────────────────────────────────

    def issue_refresh_token(self, user_id: str) -> str:
        """Issue a long-lived HS256 refresh token (7 days)."""
        now = datetime.now(tz=timezone.utc)
        payload: dict[str, Any] = {
            "sub": user_id,
            "type": "refresh",
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": now + timedelta(days=_REFRESH_TTL_DAYS),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._refresh_secret, algorithm="HS256")

    def verify_refresh_token(self, token: str) -> TokenClaims:
        """Verify HS256 refresh token. Raises if expired or invalid."""
        return self._decode(token, self._refresh_secret, algorithm="HS256", expected_type="refresh")

    def rotate_refresh_token(
        self,
        old_refresh_token: str,
        tenant_id: str,
        roles: list[Role],
    ) -> tuple[str, str]:
        """
        Validate the old refresh token and issue a new access + refresh pair.
        Old refresh token is consumed (caller must revoke JTI in DB if needed).

        Returns:
            (access_token, new_refresh_token)
        """
        claims = self.verify_refresh_token(old_refresh_token)
        new_access = self.issue_access_token(claims.user_id, tenant_id, roles)
        new_refresh = self.issue_refresh_token(claims.user_id)
        return new_access, new_refresh

    # ── Internal ──────────────────────────────────────────────────────────────

    def _decode(
        self,
        token: str,
        key: str,
        algorithm: str,
        expected_type: str,
    ) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError(str(exc)) from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError(str(exc)) from exc

        if payload.get("type") != expected_type:
            raise InvalidTokenError(
                f"Expected token type '{expected_type}', got '{payload.get('type')}'"
            )

        exp_ts = payload.get("exp", 0)
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if isinstance(exp_ts, (int, float)) else datetime.now(tz=timezone.utc)

        return TokenClaims(
            user_id=payload["sub"],
            tenant_id=payload.get("tid", ""),
            roles=[Role(r) for r in payload.get("roles", [])],
            token_type=payload["type"],
            exp=exp_dt,
            jti=payload.get("jti", ""),
        )
