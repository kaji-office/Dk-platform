"""Webhook, Audit, and Usage routes."""
from __future__ import annotations
from fastapi import APIRouter, Request, status, HTTPException, Query
from pydantic import BaseModel
from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite, RequireAdmin

# ── Webhooks ──────────────────────────────────────────────────────────────────
webhooks_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class CreateWebhookRequest(BaseModel):
    workflow_id: str
    name: str
    events: list[str] = ["execution.completed"]
    secret: str | None = None


class PatchWebhookRequest(BaseModel):
    name: str | None = None
    events: list[str] | None = None
    active: bool | None = None


@webhooks_router.get("")
async def list_webhooks(user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.webhook_service
    return {"webhooks": await svc.list(tenant_id)}


@webhooks_router.post("", status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: CreateWebhookRequest, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict = RequireWrite
) -> dict:
    svc = request.app.state.webhook_service
    return await svc.create(tenant_id, body.model_dump())


@webhooks_router.get("/{webhook_id}")
async def get_webhook(webhook_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.webhook_service
    hook = await svc.get(tenant_id, webhook_id)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return hook


@webhooks_router.patch("/{webhook_id}")
async def update_webhook(
    webhook_id: str, body: PatchWebhookRequest, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict = RequireWrite
) -> dict:
    svc = request.app.state.webhook_service
    return await svc.update(tenant_id, webhook_id, body.model_dump(exclude_none=True))


@webhooks_router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict = RequireWrite
):
    svc = request.app.state.webhook_service
    await svc.delete(tenant_id, webhook_id)


@webhooks_router.post("/inbound/{workflow_id}", status_code=status.HTTP_202_ACCEPTED)
async def inbound_webhook(workflow_id: str, request: Request) -> dict:
    """Public webhook receiver — no user auth required, validated by HMAC secret."""
    svc = request.app.state.webhook_service
    body = await request.json()
    signature = request.headers.get("X-Webhook-Signature", "")
    return await svc.handle_inbound(workflow_id, body, signature)


# ── Audit ─────────────────────────────────────────────────────────────────────
audit_router = APIRouter(prefix="/audit", tags=["Audit"])


@audit_router.get("")
async def list_audit(
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
) -> dict:
    svc = request.app.state.audit_service
    events = await svc.list(tenant_id, skip=skip, limit=limit)
    return {"events": events, "skip": skip, "limit": limit}


# ── Usage ─────────────────────────────────────────────────────────────────────
usage_router = APIRouter(prefix="/usage", tags=["Usage"])


@usage_router.get("")
async def get_usage(user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.billing_service
    return await svc.get_usage_summary(tenant_id)


# ── Schedules standalone ──────────────────────────────────────────────────────
schedules_router = APIRouter(prefix="/schedules", tags=["Schedules"])


@schedules_router.get("/{schedule_id}")
async def get_schedule(schedule_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.schedule_service
    s = await svc.get(tenant_id, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@schedules_router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: str, body: dict, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict = RequireWrite
) -> dict:
    svc = request.app.state.schedule_service
    return await svc.update(tenant_id, schedule_id, body)


@schedules_router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict = RequireWrite
):
    svc = request.app.state.schedule_service
    await svc.delete(tenant_id, schedule_id)
