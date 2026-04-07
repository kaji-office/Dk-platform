"""Auth routes — register, login, logout, token-refresh, MFA, OAuth."""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from workflow_api.limiter import limiter

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Request / Response models ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordChangeRequest(BaseModel):
    token: str
    new_password: str


class MFAVerifyRequest(BaseModel):
    code: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(body: RegisterRequest, request: Request) -> dict:
    """Register a new user account."""
    svc = request.app.state.auth_service
    try:
        user = await svc.register(email=body.email, password=body.password, full_name=body.full_name)
    except ValueError as exc:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    await request.app.state.audit_service.write(
        tenant_id=user["tenant_id"], event_type="auth.register", user_id=user["id"],
        resource_type="user", resource_id=user["id"],
        detail={"email": body.email},
    )
    return {"user_id": user["id"], "email": user["email"]}


@router.post("/login")
@limiter.limit("5/minute")
async def login(body: LoginRequest, request: Request) -> dict:
    """Authenticate and return JWT access + refresh tokens."""
    svc = request.app.state.auth_service
    try:
        tokens = await svc.login(email=body.email, password=body.password)
    except ValueError as exc:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})
    await request.app.state.audit_service.write(
        tenant_id=tokens["tenant_id"], event_type="auth.login", user_id=tokens["user_id"],
        resource_type="user", resource_id=tokens["user_id"],
        detail={"email": body.email},
    )
    return tokens  # {"access_token", "refresh_token", "expires_in"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    """Invalidate the current session / refresh token."""
    svc = request.app.state.auth_service
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    await svc.logout(token)


@router.post("/token/refresh")
async def refresh_token(body: TokenRefreshRequest, request: Request) -> dict:
    """Issue a new access token using a valid refresh token."""
    from fastapi import HTTPException
    svc = request.app.state.auth_service
    try:
        return await svc.refresh(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


@router.post("/verify-email")
async def verify_email(token: str, request: Request) -> dict:
    """Verify email address using the token sent by email."""
    from fastapi import HTTPException
    svc = request.app.state.auth_service
    try:
        await svc.verify_email(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"verified": True}


@router.post("/password/reset-request")
@limiter.limit("3/minute")
async def password_reset_request(body: PasswordResetRequest, request: Request) -> dict:
    svc = request.app.state.auth_service
    await svc.send_password_reset(body.email)
    return {"sent": True}


@router.post("/password/reset")
async def password_reset(body: PasswordChangeRequest, request: Request) -> dict:
    from fastapi import HTTPException
    svc = request.app.state.auth_service
    try:
        await svc.reset_password(body.token, body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"reset": True}


@router.post("/mfa/setup")
async def mfa_setup(request: Request) -> dict:
    """Initiate MFA TOTP setup — returns QR code URI."""
    svc = request.app.state.auth_service
    user = getattr(request.state, "user", None) or {}
    return await svc.mfa_setup(user.get("id", ""))


@router.post("/mfa/verify")
async def mfa_verify(body: MFAVerifyRequest, request: Request) -> dict:
    svc = request.app.state.auth_service
    user = getattr(request.state, "user", None) or {}
    return await svc.mfa_verify(user.get("id", ""), body.code)


@router.get("/oauth/{provider}")
async def oauth_redirect(provider: str, request: Request):
    """Initiate OAuth flow for a provider (google, github, microsoft)."""
    from fastapi import HTTPException
    svc = request.app.state.auth_service
    try:
        url = await svc.oauth_redirect_url(provider)
        return {"redirect_url": url}
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, request: Request) -> dict:
    """Handle OAuth callback and return platform tokens."""
    from fastapi import HTTPException
    svc = request.app.state.auth_service
    try:
        return await svc.oauth_exchange(provider, code)
    except NotImplementedError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
