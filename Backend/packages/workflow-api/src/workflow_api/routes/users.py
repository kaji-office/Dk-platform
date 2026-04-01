"""User routes — /users/me and API key management."""
from __future__ import annotations
from fastapi import APIRouter, Request, status
from pydantic import BaseModel
from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite

router = APIRouter(prefix="/users", tags=["Users"])


class PatchUserRequest(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class CreateAPIKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["workflows:read", "workflows:write"]
    expires_in_days: int | None = None


@router.get("/me")
async def get_me(user: CurrentUser, request: Request) -> dict:
    """Return the authenticated user's profile."""
    svc = request.app.state.user_service
    return await svc.get_profile(user["id"])


@router.patch("/me")
async def update_me(body: PatchUserRequest, user: CurrentUser, request: Request) -> dict:
    """Update the authenticated user's profile."""
    svc = request.app.state.user_service
    return await svc.update_profile(user["id"], body.model_dump(exclude_none=True))


@router.get("/me/api-keys")
async def list_api_keys(user: CurrentUser, request: Request) -> dict:
    """List all API keys for the current user."""
    svc = request.app.state.user_service
    keys = await svc.list_api_keys(user["id"])
    return {"api_keys": keys}


@router.post("/me/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(body: CreateAPIKeyRequest, user: CurrentUser, request: Request) -> dict:
    """Create a new API key. The raw key is only returned once."""
    svc = request.app.state.user_service
    return await svc.create_api_key(user["id"], body.name, body.scopes, body.expires_in_days)


@router.delete("/me/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(key_id: str, user: CurrentUser, request: Request):
    """Revoke an API key."""
    svc = request.app.state.user_service
    await svc.delete_api_key(user["id"], key_id)
