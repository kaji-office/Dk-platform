"""Workflow routes — CRUD + activate/deactivate + versions."""
from __future__ import annotations
from fastapi import APIRouter, Request, status, Query
from pydantic import BaseModel
from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite

router = APIRouter(prefix="/workflows", tags=["Workflows"])


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str | None = None
    definition: dict = {}


class PatchWorkflowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    definition: dict | None = None


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_workflows(
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
) -> dict:
    svc = request.app.state.workflow_service
    items = await svc.list(tenant_id, skip=skip, limit=limit)
    return {"workflows": items, "skip": skip, "limit": limit}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    body: CreateWorkflowRequest,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.workflow_service
    result = await svc.create(tenant_id, body.model_dump())
    await request.app.state.audit_service.write(
        tenant_id=tenant_id, event_type="workflow.created", user_id=user["id"],
        resource_type="workflow", resource_id=result.get("workflow_id"),
        detail={"name": body.name},
    )
    return result


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.workflow_service
    wf = await svc.get(tenant_id, workflow_id)
    if wf is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.patch("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: PatchWorkflowRequest,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.workflow_service
    return await svc.update(tenant_id, workflow_id, body.model_dump(exclude_none=True))


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
):
    svc = request.app.state.workflow_service
    await svc.delete(tenant_id, workflow_id)
    await request.app.state.audit_service.write(
        tenant_id=tenant_id, event_type="workflow.deleted", user_id=user["id"],
        resource_type="workflow", resource_id=workflow_id,
    )


@router.post("/{workflow_id}/activate")
async def activate_workflow(
    workflow_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.workflow_service
    return await svc.set_active(tenant_id, workflow_id, active=True)


@router.post("/{workflow_id}/deactivate")
async def deactivate_workflow(
    workflow_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.workflow_service
    return await svc.set_active(tenant_id, workflow_id, active=False)


# ── Versions ──────────────────────────────────────────────────────────────────

@router.get("/{workflow_id}/versions")
async def list_versions(workflow_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.workflow_service
    versions = await svc.list_versions(tenant_id, workflow_id)
    return {"versions": versions}


@router.get("/{workflow_id}/versions/{version_no}")
async def get_version(workflow_id: str, version_no: int, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.workflow_service
    return await svc.get_version(tenant_id, workflow_id, version_no)


@router.post("/{workflow_id}/versions/{version_no}/restore")
async def restore_version(
    workflow_id: str,
    version_no: int,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.workflow_service
    return await svc.restore_version(tenant_id, workflow_id, version_no)


# ── Schedules ─────────────────────────────────────────────────────────────────

@router.get("/{workflow_id}/schedules")
async def list_schedules(workflow_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.schedule_service
    items = await svc.list(tenant_id, workflow_id)
    return {"schedules": items}


@router.post("/{workflow_id}/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    workflow_id: str,
    body: dict,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.schedule_service
    result = await svc.create(tenant_id, workflow_id, body)
    await request.app.state.audit_service.write(
        tenant_id=tenant_id, event_type="schedule.created", user_id=user["id"],
        resource_type="schedule", resource_id=result.get("schedule_id"),
        detail={"workflow_id": workflow_id, "cron_expression": body.get("cron_expression")},
    )
    return result
