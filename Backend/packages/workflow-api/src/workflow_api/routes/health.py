"""Health check routes — no auth required."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def health(request: Request):
    """Returns 200 when the API process is running."""
    return {"status": "ok", "service": "workflow-api"}


@router.get("/health/ready", summary="Readiness probe")
async def health_ready(request: Request):
    """Returns 200 when all downstream dependencies are reachable."""
    checks: dict = {}
    ready = True

    # Check each injectable service if present
    state = request.app.state
    if hasattr(state, "mongo_client"):
        try:
            await state.mongo_client.admin.command("ping")
            checks["mongodb"] = "ok"
        except Exception as e:
            checks["mongodb"] = f"error: {e}"
            ready = False

    status_code = 200 if ready else 503
    return JSONResponse(
        content={"status": "ready" if ready else "degraded", "checks": checks},
        status_code=status_code,
    )
