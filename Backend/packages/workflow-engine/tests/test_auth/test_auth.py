import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest
import jwt
import httpx

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
from workflow_engine.auth.api_key_service import APIKeyService
from workflow_engine.auth.rbac import RBACGuard, require_role
from workflow_engine.errors import (
    AuthenticationError,
    TokenExpiredError,
    InvalidTokenError,
    InsufficientPermissionsError,
)

# --- Test Data Setup ---

# Generate keys for testing JWT
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_KEY = private_key_obj.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode()

public_key_obj = private_key_obj.public_key()
PUBLIC_KEY = public_key_obj.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

REFRESH_SECRET = "test-refresh-secret-12345"


@pytest.fixture
def jwt_service():
    return JWTService(PRIVATE_KEY, PUBLIC_KEY, REFRESH_SECRET)


# --- JWTService Tests ---

def test_jwt_access_token(jwt_service):
    user_id = str(uuid.uuid4())
    tenant_id = "tenant-1"
    roles = [Role.VIEWER, Role.EDITOR]
    
    token = jwt_service.issue_access_token(user_id, tenant_id, roles)
    assert isinstance(token, str)
    
    claims = jwt_service.verify_access_token(token)
    assert claims.user_id == user_id
    assert claims.tenant_id == tenant_id
    assert claims.roles == roles
    assert claims.token_type == "access"

def test_jwt_refresh_token(jwt_service):
    user_id = str(uuid.uuid4())
    
    token = jwt_service.issue_refresh_token(user_id)
    assert isinstance(token, str)
    
    claims = jwt_service.verify_refresh_token(token)
    assert claims.user_id == user_id
    assert claims.token_type == "refresh"

def test_jwt_rotate_refresh_token(jwt_service):
    user_id = str(uuid.uuid4())
    old_refresh = jwt_service.issue_refresh_token(user_id)
    
    new_access, new_refresh = jwt_service.rotate_refresh_token(old_refresh, "t1", [Role.VIEWER])
    
    assert isinstance(new_access, str)
    assert isinstance(new_refresh, str)
    
    acc_claims = jwt_service.verify_access_token(new_access)
    ref_claims = jwt_service.verify_refresh_token(new_refresh)
    
    assert acc_claims.user_id == user_id
    assert ref_claims.user_id == user_id

def test_jwt_expired_token(jwt_service):
    # Manually create an expired token
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": "user1",
        "type": "access",
        "iss": "dk-platform",
        "aud": "dk-platform-api",
        "iat": now - timedelta(minutes=30),
        "exp": now - timedelta(minutes=15),
    }
    expired_token = jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")
    
    with pytest.raises(TokenExpiredError):
        jwt_service.verify_access_token(expired_token)

def test_jwt_invalid_token(jwt_service):
    with pytest.raises(InvalidTokenError):
        jwt_service.verify_access_token("this-is-not-a-token")
        
    # Verify signature failure because refresh token is signed with HS256 not RS256
    user_id = str(uuid.uuid4())
    refresh = jwt_service.issue_refresh_token(user_id)
    with pytest.raises(InvalidTokenError):
        jwt_service.verify_access_token(refresh)


# --- PasswordService Tests ---

def test_password_hash_and_verify():
    plain = "SuperSecret123!"
    hashed = PasswordService.hash(plain)
    
    assert PasswordService.verify(plain, hashed)
    assert not PasswordService.verify("WrongPassword", hashed)

def test_password_strength():
    # Valid
    res = PasswordService.validate_strength("StrongPassw0rd!")
    assert res.is_valid
    assert len(res.errors) == 0
    
    # Too short
    res = PasswordService.validate_strength("Short1!")
    assert not res.is_valid
    assert any("12 characters" in e for e in res.errors)
    
    # Missing uppercase
    res = PasswordService.validate_strength("nouppercase123!")
    assert not res.is_valid
    assert any("uppercase" in e for e in res.errors)
    
    # Common password
    res = PasswordService.validate_strength("Password123!") # Assume 'password' is in common list
    # The current code checks plain.lower() in _COMMON_PASSWORDS.
    # We might need to adjust the test if it doesn't match exactly.
    # Let's check a direct common password.
    res2 = PasswordService.validate_strength("password123!")
    # Wait, the check is `plain.lower() in _COMMON_PASSWORDS`. "password123!" might not be in the set.
    res3 = PasswordService.validate_strength("password1")
    assert not res3.is_valid
    assert any("common" in e for e in res3.errors)
    

# --- APIKeyService Tests ---

def test_api_key_create():
    raw_key, record = APIKeyService.create("t1", "Test Key", ["workflows:read"])
    
    assert raw_key.startswith("wfk_")
    assert len(raw_key) > 30
    assert record.tenant_id == "t1"
    assert record.name == "Test Key"
    assert record.scopes == ["workflows:read"]
    assert record.prefix == raw_key[:12]
    
def test_api_key_invalid_scope():
    with pytest.raises(ValueError):
        APIKeyService.create("t1", "Bad Key", ["invalid:scope"])

def test_api_key_verify():
    raw_key, record = APIKeyService.create("t1", "Test Key", ["workflows:read"])
    raw_key2, record2 = APIKeyService.create("t1", "Test Key 2", ["executions:read"])
    
    records = [record, record2]
    
    # Valid verify
    verified = APIKeyService.verify(raw_key, records)
    assert verified is not None
    assert verified.key_id == record.key_id
    
    # Invalid verify
    assert APIKeyService.verify("wfk_invalidkey", records) is None
    
    # Not wfk_ prefix
    assert APIKeyService.verify("somethingelse", records) is None
    
    # Revoked
    revoked_record = APIKeyService.revoke(record)
    assert APIKeyService.verify(raw_key, [revoked_record]) is None

def test_api_key_check_scope():
    _, record = APIKeyService.create("t1", "Key", ["workflows:read"])
    
    # Should not raise
    APIKeyService.check_scope(record, "workflows:read")
    
    # Should raise
    with pytest.raises(InsufficientPermissionsError):
        APIKeyService.check_scope(record, "workflows:write")
        
    # Admin scope bypass
    _, admin_record = APIKeyService.create("t1", "Admin Key", ["admin"])
    APIKeyService.check_scope(admin_record, "anything") # Shouldn't raise


# --- MFAService Tests ---

def test_mfa_setup_and_verify():
    setup = MFAService.setup("user1")
    
    assert len(setup.secret) > 0
    assert setup.provisioning_uri.startswith("otpauth://")
    assert len(setup.backup_codes) == 8
    
    # Note: Testing TOTP verify is tricky because it depends on time.
    # We can generate a code for 'now' and verify it.
    import pyotp
    totp = pyotp.TOTP(setup.secret)
    valid_code = totp.now()
    
    assert MFAService.verify(setup.secret, valid_code)
    assert not MFAService.verify(setup.secret, "000000")

def test_mfa_backup_codes():
    setup = MFAService.setup("user1")
    plain_codes = setup.backup_codes
    
    hashed_codes = MFAService.hash_backup_codes(plain_codes)
    assert len(hashed_codes) == 8
    assert all(not bc.used for bc in hashed_codes)
    
    # Verify valid code
    success, updated_codes = MFAService.verify_backup_code(plain_codes[0], hashed_codes)
    assert success
    assert MFAService.remaining_backup_codes(updated_codes) == 7
    # Check it was marked used
    used_bc = next(bc for bc in updated_codes if bc.code_hash == hashed_codes[0].code_hash)
    assert used_bc.used
    
    # Verify already used code
    success2, updated_codes2 = MFAService.verify_backup_code(plain_codes[0], updated_codes)
    assert not success2
    
    # Verify invalid code
    success3, updated_codes3 = MFAService.verify_backup_code("invalidcode", updated_codes)
    assert not success3


# --- RBAC Tests ---

def test_rbac_check():
    assert RBACGuard.check([Role.EDITOR], Role.VIEWER)
    assert RBACGuard.check([Role.EDITOR], Role.EDITOR)
    assert not RBACGuard.check([Role.EDITOR], Role.ADMIN)
    assert RBACGuard.check([Role.VIEWER, Role.ADMIN], Role.EDITOR)
    
def test_rbac_require():
    # Should not raise
    RBACGuard.require([Role.ADMIN], Role.EDITOR)
    
    # Should raise
    with pytest.raises(InsufficientPermissionsError):
        RBACGuard.require([Role.VIEWER], Role.EDITOR)

@pytest.mark.asyncio
async def test_rbac_decorator_async():
    class Service:
        @require_role(Role.EDITOR)
        async def do_something(self, claims: TokenClaims):
            return True
            
    srv = Service()
    
    # Valid
    claims_valid = TokenClaims("u1", "t1", [Role.ADMIN], "access", datetime.now(), "j1")
    assert await srv.do_something(claims_valid)
    
    # Invalid
    claims_invalid = TokenClaims("u1", "t1", [Role.VIEWER], "access", datetime.now(), "j1")
    with pytest.raises(InsufficientPermissionsError):
        await srv.do_something(claims_invalid)
        
def test_rbac_decorator_sync():
    class Service:
        @require_role(Role.EDITOR)
        def do_something(self, claims: TokenClaims):
            return True
            
    srv = Service()
    
    claims_valid = TokenClaims("u1", "t1", [Role.ADMIN], "access", datetime.now(), "j1")
    assert srv.do_something(claims_valid)


# --- OAuthService Tests ---

@pytest.fixture
def oauth_creds():
    return {
        "google": OAuthCredentials("client-uid", "client-sec", "http://redirect")
    }

def test_oauth_get_auth_url(oauth_creds):
    service = OAuthService(oauth_creds)
    
    url = service.get_authorization_url("google", "state-123")
    assert "https://accounts.google.com" in url
    assert "client_id=client-uid" in url
    assert "state=state-123" in url
    
    with pytest.raises(AuthenticationError):
        service.get_authorization_url("github", "state-123") # Not configured

@pytest.mark.asyncio
async def test_oauth_exchange_code(oauth_creds):
    service = OAuthService(oauth_creds)
    
    class MockResponse:
        def __init__(self, json_data, status=200):
            self.status_code = status
            self._json = json_data
        def json(self):
            return self._json

    mock_token_resp = MockResponse({"access_token": "acc_tok", "refresh_token": "ref_tok"})
    
    mock_profile_resp = MockResponse({
        "sub": "user-123",
        "email": "test@google.com",
        "name": "Test User",
        "picture": "http://img.png"
    })

    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, *args, **kwargs):
            return mock_token_resp
        async def get(self, *args, **kwargs):
            return mock_profile_resp

    with patch("workflow_engine.auth.oauth_service.httpx.AsyncClient", return_value=MockAsyncClient()):
        profile, tokens = await service.exchange_code("google", "code-xyz", "state-123")
        
        assert tokens["access_token"] == "acc_tok"
        assert profile.provider == "google"
        assert profile.provider_user_id == "user-123"
        assert profile.email == "test@google.com"

@pytest.mark.asyncio
async def test_oauth_refresh_token(oauth_creds):
    service = OAuthService(oauth_creds)
    
    class MockResponse:
        def __init__(self, json_data, status=200):
            self.status_code = status
            self._json = json_data
        def json(self):
            return self._json

    mock_token_resp = MockResponse({"access_token": "new_acc_tok"})
    
    class MockAsyncClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def post(self, *args, **kwargs):
            return mock_token_resp

    with patch("workflow_engine.auth.oauth_service.httpx.AsyncClient", return_value=MockAsyncClient()):
        tokens = await service.refresh_oauth_token("google", "old_ref_tok")
        assert tokens["access_token"] == "new_acc_tok"
