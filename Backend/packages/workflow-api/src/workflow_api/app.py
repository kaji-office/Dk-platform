"""
workflow-api FastAPI application factory.

Middleware stack (in spec order):
  1. RequestIDMiddleware       — X-Request-ID injection
  2. CORSMiddleware            — origin/header control
  3. SlowAPI rate-limiter      — per-tenant 429 with Retry-After
  4. ResponseEnvelopeMiddleware— {success, request_id, data} wrapping

Auth and tenant resolution happen inside dependencies, not middleware,
so they have access to the validated request body and path parameters.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request, status

# Configure structured JSON logging at import time so all loggers (including
# uvicorn's access logger) emit JSON from the very first request.
try:
    from workflow_engine.observability.logging import configure_structured_logging
    _log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    configure_structured_logging(level=_log_level)
except Exception:
    logging.basicConfig(level=logging.INFO)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from workflow_api.limiter import limiter
from workflow_api.middleware.common import RequestIDMiddleware, ResponseEnvelopeMiddleware
from workflow_api.routes.health import router as health_router
from workflow_api.routes.auth import router as auth_router
from workflow_api.routes.users import router as users_router
from workflow_api.routes.workflows import router as workflows_router
from workflow_api.routes.executions import router as executions_router
from workflow_api.routes.webhooks import (
    webhooks_router,
    audit_router,
    usage_router,
    schedules_router,
)
from workflow_api.websocket.execution_ws import router as ws_router
from workflow_api.routes.chat import router as chat_router

def create_app(
    cors_origins: list[str] | None = None,
    services: dict | None = None,
) -> FastAPI:
    """
    Application factory.

    Args:
        cors_origins: Allowed CORS origins. Read from CORS_ORIGINS env var (comma-separated).
                      Credentials + wildcard origin is rejected by browsers — must be explicit.
        services:     Dict of service objects injected into app.state
                      (auth_service, workflow_service, execution_service, ...).
    """
    # Resolve CORS origins — explicit list required; wildcard+credentials is browser-blocked
    if cors_origins is None:
        env_origins = os.environ.get("CORS_ORIGINS", "")
        if env_origins:
            cors_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
        else:
            # Dev fallback only — acceptable without credentials in local env
            cors_origins = ["http://localhost:3000", "http://127.0.0.1:3000", "http://192.168.1.93:3000","http://192.168.1.93:5173", "http://192.168.1.93:5174"]

    app = FastAPI(
        title="DK Workflow API",
        version="1.0.0",
        description="AI Workflow Builder — REST Gateway",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware (added innermost-first in Starlette) ────────────────────

    # 1. Request ID (outermost — first to see request, last to see response)
    app.add_middleware(RequestIDMiddleware)

    # 2. CORS — explicit origin list required (wildcard + credentials is browser-blocked)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key", "X-Tenant-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    # 3. Rate limiter state & middleware
    app.state.limiter = limiter
    
    async def custom_rate_limit_handler(r: Request, exc: RateLimitExceeded):
        resp = _rate_limit_exceeded_handler(r, exc)
        resp.headers["Retry-After"] = "60"
        return resp
        
    app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    # 4. Response envelope (innermost — runs after route handlers)
    app.add_middleware(ResponseEnvelopeMiddleware)

    # ── Inject service dependencies ────────────────────────────────────────
    if services:
        for name, svc in services.items():
            setattr(app.state, name, svc)

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router,       prefix="/api/v1")
    app.include_router(users_router,      prefix="/api/v1")
    app.include_router(workflows_router,  prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(webhooks_router,   prefix="/api/v1")
    app.include_router(audit_router,      prefix="/api/v1")
    app.include_router(usage_router,      prefix="/api/v1")
    app.include_router(schedules_router,  prefix="/api/v1")
    app.include_router(ws_router,         prefix="/api/v1")
    app.include_router(chat_router,       prefix="/api/v1")

    # ── Global error handler ───────────────────────────────────────────────
    import logging as _logging
    _logger = _logging.getLogger("dk.api")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        _logger.exception(
            "Unhandled exception on %s %s (request_id=%s) — %s: %s",
            request.method,
            request.url.path,
            request_id,
            type(exc).__name__,
            exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "request_id": request_id, "detail": "Internal server error"},
        )

    return app


# Default app instance for uvicorn
app = create_app()
