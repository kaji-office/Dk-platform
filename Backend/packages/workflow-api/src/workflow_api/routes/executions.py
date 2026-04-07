"""Execution routes — trigger, list, get, cancel, retry, logs, nodes, human-input."""
from __future__ import annotations
import json as _json
from fastapi import APIRouter, Header, Request, status, Query, HTTPException
from pydantic import BaseModel
from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite

router = APIRouter(tags=["Executions"])


class TriggerRequest(BaseModel):
    input_data: dict = {}
    triggered_by: str | None = None


class HumanInputRequest(BaseModel):
    run_id: str
    node_id: str
    response: dict


# ── Trigger ───────────────────────────────────────────────────────────────────

@router.post("/workflows/{workflow_id}/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_execution(
    workflow_id: str,
    body: TriggerRequest,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    """Enqueue a workflow execution. Returns run_id immediately (async).

    Supply `Idempotency-Key: <uuid>` to prevent duplicate runs on network retries.
    A matching key returns the original run within 24 hours.
    """
    # Idempotency check — serve cached result if key already seen
    if idempotency_key:
        redis = getattr(request.app.state, "redis_client", None)
        if redis:
            cache_key = f"idempotent:{tenant_id}:{idempotency_key}"
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return _json.loads(cached)
            except Exception:
                pass  # Redis unavailable — fall through, accept the risk of duplication

    svc = request.app.state.execution_service
    run = await svc.trigger(tenant_id, workflow_id, body.input_data, triggered_by=user["id"])
    result = {"run_id": run["run_id"], "status": "queued"}

    # Cache under idempotency key for 24 hours
    if idempotency_key:
        redis = getattr(request.app.state, "redis_client", None)
        if redis:
            try:
                await redis.setex(cache_key, 86400, _json.dumps(result))
            except Exception:
                pass

    await request.app.state.audit_service.write(
        tenant_id=tenant_id, event_type="execution.triggered", user_id=user["id"],
        resource_type="execution", resource_id=run["run_id"],
        detail={"workflow_id": workflow_id},
    )
    return result


# ── List / Get ────────────────────────────────────────────────────────────────

@router.get("/executions")
async def list_executions(
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    workflow_id: str | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
) -> dict:
    svc = request.app.state.execution_service
    items = await svc.list(tenant_id, workflow_id=workflow_id, skip=skip, limit=limit)
    return {"executions": items, "skip": skip, "limit": limit}


@router.get("/executions/{run_id}")
async def get_execution(run_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.execution_service
    run = await svc.get(tenant_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return run


# ── Cancel / Retry ────────────────────────────────────────────────────────────

@router.post("/executions/{run_id}/cancel")
async def cancel_execution(
    run_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.execution_service
    try:
        return await svc.cancel(tenant_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/executions/{run_id}/retry")
async def retry_execution(
    run_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    _: dict = RequireWrite,
) -> dict:
    svc = request.app.state.execution_service
    try:
        return await svc.retry(tenant_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Nodes ─────────────────────────────────────────────────────────────────────

@router.get("/executions/{run_id}/nodes")
async def list_nodes(run_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    svc = request.app.state.execution_service
    nodes = await svc.list_nodes(tenant_id, run_id)
    return {"nodes": nodes}


@router.post("/executions/human-input", status_code=status.HTTP_202_ACCEPTED)
async def submit_human_input(body: HumanInputRequest, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict:
    """Submit a human approval/response for a paused execution node."""
    svc = request.app.state.execution_service
    try:
        return await svc.submit_human_input(tenant_id, body.run_id, body.node_id, body.response)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Logs ──────────────────────────────────────────────────────────────────────

@router.get("/executions/{run_id}/logs")
async def get_logs(
    run_id: str,
    user: CurrentUser,
    tenant_id: TenantId,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
) -> dict:
    svc = request.app.state.execution_service
    logs = await svc.get_logs(tenant_id, run_id, skip=skip, limit=limit)
    return {"logs": logs, "run_id": run_id}
