"""Health check routes — no auth required."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health(request: Request):
    """Returns 200 when the API process is running."""
    return {"status": "ok", "service": "workflow-api"}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready(request: Request):
    """Returns 200 when all downstream dependencies (MongoDB, PostgreSQL, Redis) are reachable."""
    checks: dict = {}
    ready = True
    state = request.app.state

    # MongoDB
    if hasattr(state, "mongo_db"):
        try:
            await state.mongo_db.command("ping")
            checks["mongodb"] = "ok"
        except Exception as exc:
            checks["mongodb"] = f"error: {exc}"
            ready = False
    elif hasattr(state, "mongo_client"):
        try:
            await state.mongo_client.admin.command("ping")
            checks["mongodb"] = "ok"
        except Exception as exc:
            checks["mongodb"] = f"error: {exc}"
            ready = False
    else:
        checks["mongodb"] = "not_configured"

    # PostgreSQL (via repos on app.state)
    if hasattr(state, "repos") and hasattr(state.repos, "users"):
        try:
            await state.repos.users._pool.fetchval("SELECT 1")
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error: {exc}"
            ready = False
    else:
        checks["postgres"] = "not_configured"

    # Redis
    if hasattr(state, "redis_client"):
        try:
            await state.redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            ready = False
    else:
        checks["redis"] = "not_configured"

    status_code = 200 if ready else 503
    return JSONResponse(
        content={"status": "ready" if ready else "degraded", "checks": checks},
        status_code=status_code,
    )


@router.get("/metrics", summary="Prometheus metrics", include_in_schema=False)
async def metrics():
    """Expose Prometheus metrics for scraping by the monitoring stack."""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except ImportError:
        return JSONResponse(status_code=501, content={"detail": "prometheus_client not installed"})
