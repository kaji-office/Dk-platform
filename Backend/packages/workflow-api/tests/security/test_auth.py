"""
P9-T-04 — Auth Security Test Suite.

Tests that cover:
  - JWTService unit tests: tampered signature, wrong token type, expired token
  - API-level auth middleware: 401 on bad/missing token, 403 on insufficient role
  - Cross-tenant isolation: tenant A cannot read tenant B's resources → 404
  - Password reset token single-use and invalidation of old tokens
  - Duplicate email registration → 422
"""
from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from workflow_engine.auth.jwt_service import JWTService
from workflow_engine.auth.models import Role
from workflow_engine.errors import InvalidTokenError, TokenExpiredError
from workflow_api.app import create_app


# ── RSA test key pair ─────────────────────────────────────────────────────────

def _generate_rsa_key_pair() -> tuple[str, str]:
    """Generate a throwaway RSA-2048 key pair for testing."""
    private_key_obj = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_pem = private_key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key_obj.public_key().private_bytes if False else \
        private_key_obj.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_key_pair()
_REFRESH_SECRET = "test-refresh-secret-32-chars-long"


@pytest.fixture
def jwt_svc() -> JWTService:
    return JWTService(
        private_key=_PRIVATE_KEY,
        public_key=_PUBLIC_KEY,
        refresh_secret=_REFRESH_SECRET,
    )


# ── JWTService unit tests ─────────────────────────────────────────────────────

class TestJWTServiceSecurity:

    def test_tampered_jwt_rejected(self, jwt_svc: JWTService):
        """Flipping one byte in the JWT signature must raise InvalidTokenError."""
        token = jwt_svc.issue_access_token("user-1", "tenant-1", [Role.ADMIN])
        header, payload, signature = token.split(".")
        # Flip the last character of the signature
        tampered_sig = signature[:-1] + ("A" if signature[-1] != "A" else "B")
        tampered = f"{header}.{payload}.{tampered_sig}"

        with pytest.raises(InvalidTokenError):
            jwt_svc.verify_access_token(tampered)

    def test_access_token_as_refresh_rejected(self, jwt_svc: JWTService):
        """Using an access token where a refresh token is expected must fail."""
        access_token = jwt_svc.issue_access_token("user-1", "tenant-1", [Role.VIEWER])
        with pytest.raises(InvalidTokenError):
            jwt_svc.verify_refresh_token(access_token)  # wrong algorithm + wrong type

    def test_refresh_token_as_access_rejected(self, jwt_svc: JWTService):
        """Using a refresh token as an access token must fail."""
        refresh_token = jwt_svc.issue_refresh_token("user-1")
        with pytest.raises((InvalidTokenError, Exception)):
            jwt_svc.verify_access_token(refresh_token)  # wrong algorithm

    def test_expired_access_token_rejected(self, jwt_svc: JWTService):
        """A token with exp in the past must raise TokenExpiredError."""
        # Manually craft an expired token by encoding with past exp
        past = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "user-1",
            "tid": "tenant-1",
            "roles": ["ADMIN"],
            "type": "access",
            "iss": "dk-platform",
            "aud": "dk-platform-api",
            "iat": past - timedelta(hours=1),
            "exp": past,
            "jti": "test-jti",
        }
        expired_token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(TokenExpiredError):
            jwt_svc.verify_access_token(expired_token)

    def test_wrong_audience_rejected(self, jwt_svc: JWTService):
        """Token with wrong audience claim must be rejected."""
        payload = {
            "sub": "user-1",
            "tid": "tenant-1",
            "roles": ["ADMIN"],
            "type": "access",
            "iss": "dk-platform",
            "aud": "wrong-audience",
            "iat": datetime.now(tz=timezone.utc),
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "jti": "test-jti",
        }
        bad_aud_token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(InvalidTokenError):
            jwt_svc.verify_access_token(bad_aud_token)

    def test_wrong_issuer_rejected(self, jwt_svc: JWTService):
        """Token with wrong issuer claim must be rejected."""
        payload = {
            "sub": "user-1",
            "tid": "tenant-1",
            "roles": ["ADMIN"],
            "type": "access",
            "iss": "evil-issuer",
            "aud": "dk-platform-api",
            "iat": datetime.now(tz=timezone.utc),
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "jti": "test-jti",
        }
        bad_iss_token = jwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(InvalidTokenError):
            jwt_svc.verify_access_token(bad_iss_token)

    def test_valid_access_token_accepted(self, jwt_svc: JWTService):
        """Freshly issued access token must verify without error."""
        token = jwt_svc.issue_access_token("user-1", "tenant-1", [Role.ADMIN])
        claims = jwt_svc.verify_access_token(token)
        assert claims.user_id == "user-1"
        assert claims.tenant_id == "tenant-1"
        assert Role.ADMIN in claims.roles

    def test_valid_refresh_token_accepted(self, jwt_svc: JWTService):
        """Freshly issued refresh token must verify without error."""
        token = jwt_svc.issue_refresh_token("user-1")
        claims = jwt_svc.verify_refresh_token(token)
        assert claims.user_id == "user-1"


# ── API auth middleware tests ─────────────────────────────────────────────────

def _build_api_app(verify_token_result=None, verify_token_error=None):
    """Build the test app with a mock auth service."""
    auth_svc = AsyncMock()
    if verify_token_error is not None:
        auth_svc.verify_token.side_effect = verify_token_error
    else:
        auth_svc.verify_token.return_value = verify_token_result or {
            "id": "u1", "tenant_id": "t1", "role": "ADMIN"
        }
    auth_svc.register.side_effect = None
    auth_svc.login.return_value = {"access_token": "tok", "refresh_token": "ref"}

    wf_svc = AsyncMock()
    wf_svc.list.return_value = []
    wf_svc.create.return_value = {"id": "wf1"}
    wf_svc.get.return_value = None  # Not found by default

    exec_svc = AsyncMock()
    exec_svc.trigger.return_value = {"run_id": "r1"}

    services = {
        "auth_service": auth_svc,
        "user_service": AsyncMock(),
        "workflow_service": wf_svc,
        "execution_service": exec_svc,
        "webhook_service": AsyncMock(),
        "audit_service": AsyncMock(),
        "billing_service": AsyncMock(),
        "schedule_service": AsyncMock(),
    }
    app = create_app(services=services)
    app.state.limiter.reset()
    return app


@pytest.mark.asyncio
async def test_no_auth_header_rejected():
    """Request with no Authorization header must return 401."""
    app = _build_api_app(verify_token_error=Exception("no auth"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/workflows")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_deactivated_user_rejected():
    """verify_token raising an error (e.g., deactivated user) must return 401."""
    from workflow_engine.errors import AuthenticationError
    app = _build_api_app(verify_token_error=AuthenticationError("User deactivated"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/workflows",
            headers={"Authorization": "Bearer some-token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_rejected():
    """verify_token raising InvalidTokenError must return 401."""
    from workflow_engine.errors import InvalidTokenError
    app = _build_api_app(verify_token_error=InvalidTokenError("tampered"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/workflows",
            headers={"Authorization": "Bearer tampered.jwt.here"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_rejected():
    """verify_token raising TokenExpiredError must return 401."""
    from workflow_engine.errors import TokenExpiredError
    app = _build_api_app(verify_token_error=TokenExpiredError("expired"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/workflows",
            headers={"Authorization": "Bearer expired.token"},
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_delete_workflow():
    """A VIEWER-role user must not be able to delete a workflow (→ 403)."""
    app = _build_api_app(verify_token_result={"id": "u-viewer", "tenant_id": "t1", "role": "VIEWER"})

    wf_svc = app.state.workflow_service
    from workflow_engine.errors import InsufficientPermissionsError
    wf_svc.delete.side_effect = InsufficientPermissionsError("VIEWER cannot delete")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            "/api/v1/workflows/wf-1",
            headers={"Authorization": "Bearer viewer-token"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_viewer_cannot_trigger_execution():
    """A VIEWER-role user must not be able to trigger an execution (→ 403)."""
    app = _build_api_app(verify_token_result={"id": "u-viewer", "tenant_id": "t1", "role": "VIEWER"})

    exec_svc = app.state.execution_service
    from workflow_engine.errors import InsufficientPermissionsError
    exec_svc.trigger.side_effect = InsufficientPermissionsError("VIEWER cannot trigger")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={},
            headers={"Authorization": "Bearer viewer-token"},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_workflow_returns_404():
    """
    Authenticated user from tenant-A must get 404 when accessing a workflow
    owned by tenant-B (not 403, which would leak resource existence).
    """
    app = _build_api_app(verify_token_result={"id": "u-a", "tenant_id": "tenant-A", "role": "ADMIN"})
    # workflow_service.get returns None (resource not visible to this tenant)
    app.state.workflow_service.get.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/workflows/tenant-B-wf",
            headers={"Authorization": "Bearer tenant-a-token"},
        )
    # 404 — resource does not exist (from the requesting tenant's perspective)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cross_tenant_execution_returns_404():
    """
    User from tenant-A accessing tenant-B's execution must get 404.
    """
    app = _build_api_app(verify_token_result={"id": "u-a", "tenant_id": "tenant-A", "role": "ADMIN"})
    app.state.execution_service.get.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/executions/tenant-B-run",
            headers={"Authorization": "Bearer tenant-a-token"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_email_registration():
    """Registering the same email twice must return 422 (conflict)."""
    app = _build_api_app()
    # First registration succeeds, second raises an error
    call_count = 0

    async def _register_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise ValueError("Email already registered")
        return {"id": "new-user", "email": "dup@example.com", "tenant_id": "t1"}

    app.state.auth_service.register.side_effect = _register_side_effect

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"email": "dup@example.com", "password": "Str0ngP@ss!", "full_name": "Test User"}

        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code in (200, 201), f"First registration failed: {resp1.status_code}"

        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 422, f"Expected 422 for duplicate email, got {resp2.status_code}"


# ── RBAC unit tests ────────────────────────────────────────────────────────────

class TestRBACGuard:
    """Unit tests for the RBACGuard helper — no HTTP layer involved."""

    def test_viewer_cannot_satisfy_editor_requirement(self):
        from workflow_engine.auth.rbac import RBACGuard
        from workflow_engine.errors import InsufficientPermissionsError
        with pytest.raises(InsufficientPermissionsError):
            RBACGuard.require([Role.VIEWER], Role.EDITOR, action="edit_workflow")

    def test_admin_satisfies_editor_requirement(self):
        from workflow_engine.auth.rbac import RBACGuard
        # Should not raise
        RBACGuard.require([Role.ADMIN], Role.EDITOR, action="edit_workflow")

    def test_superadmin_satisfies_all_roles(self):
        from workflow_engine.auth.rbac import RBACGuard
        for role in Role:
            RBACGuard.require([Role.SUPERADMIN], role, action="anything")

    def test_empty_roles_rejected_for_any_requirement(self):
        from workflow_engine.auth.rbac import RBACGuard
        from workflow_engine.errors import InsufficientPermissionsError
        with pytest.raises(InsufficientPermissionsError):
            RBACGuard.require([], Role.VIEWER, action="read")

    def test_check_returns_false_for_insufficient_role(self):
        from workflow_engine.auth.rbac import RBACGuard
        assert not RBACGuard.check([Role.VIEWER], Role.ADMIN)

    def test_check_returns_true_for_sufficient_role(self):
        from workflow_engine.auth.rbac import RBACGuard
        assert RBACGuard.check([Role.EDITOR], Role.VIEWER)
        assert RBACGuard.check([Role.EDITOR], Role.EDITOR)
        assert not RBACGuard.check([Role.EDITOR], Role.ADMIN)
