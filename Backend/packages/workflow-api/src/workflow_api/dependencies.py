"""
Shared FastAPI dependencies — auth, tenant resolution, rate limiting.
All actual logic lives in workflow-engine SDK; this is a thin wiring layer.
"""
from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ── Sentinel user roles ───────────────────────────────────────────────────────
ROLES_WRITE = {"OWNER", "EDITOR", "ADMIN"}
ROLES_READ  = {"OWNER", "EDITOR", "VIEWER", "ADMIN"}

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict[str, Any]:
    """
    Resolve the calling user from either:
      - Authorization: Bearer <jwt>
      - X-API-Key: wfk_...

    Injects a user dict onto request.state.user.
    Raises HTTP 401 if neither credential is present or valid.
    """
    # Short-circuit for test injection
    if hasattr(request.state, "user"):
        return request.state.user

    token: str | None = None
    if credentials:
        token = credentials.credentials
    elif x_api_key:
        token = x_api_key

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Delegate verification to the engine SDK JWTService / APIKeyService
    # In production, this calls the injected auth service from app state
    auth_service = request.app.state.auth_service
    try:
        user = await auth_service.verify_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.user = user
    return user


# Shorthand for route signatures
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def require_role(*allowed_roles: str) -> Any:
    """Factory: returns a dependency that enforces one of the allowed roles."""

    async def _check(user: CurrentUser) -> dict[str, Any]:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.get('role')}' is not permitted for this action",
            )
        return user

    return Depends(_check)


# Convenience shorthands
RequireWrite = require_role("OWNER", "EDITOR", "ADMIN")
RequireAdmin = require_role("OWNER", "ADMIN")


def get_tenant_id(user: CurrentUser) -> str:
    """Extract tenant_id from authenticated user context."""
    tid = user.get("tenant_id")
    if not tid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing tenant_id in token")
    return tid


TenantId = Annotated[str, Depends(get_tenant_id)]
