"""
Middleware stack for the DK workflow-api.

Order (outermost → innermost):
  1. RequestIDMiddleware   — injects X-Request-ID into every request/response
  2. CORSMiddleware        — (added via FastAPI add_middleware in app.py)
  3. ResponseEnvelopeMiddleware — wraps 2xx JSON responses in {success, data, request_id}
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique X-Request-ID header into every request and response.
    Uses incoming value if already present (idempotent for upstream proxies).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Attach to request state for downstream access
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """
    Wraps successful JSON responses in a standard envelope:

        {
            "success": true,
            "request_id": "<uuid>",
            "data": { ... original response body ... }
        }

    Error responses (4xx/5xx) are passed through as-is.
    Non-JSON responses (WebSocket upgrades, health checks) are untouched.
    """

    # Routes excluded from envelope wrapping
    SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # For 429 Rate Limit Exceeded, ensure Retry-After is present
        if response.status_code == 429:
            response.headers["Retry-After"] = "60"

        # Skip non-JSON, errors, WebSocket upgrades, and excluded paths
        if (
            request.url.path in self.SKIP_PATHS
            or response.status_code >= 400
            or "application/json" not in response.headers.get("content-type", "")
            or response.status_code == 101  # WebSocket upgrade
        ):
            return response

        # Read and re-wrap the body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        try:
            original = json.loads(body)
        except Exception:
            return response  # Not valid JSON, pass through

        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        wrapped = {"success": True, "request_id": request_id, "data": original}

        # Exclude content-length — JSONResponse recomputes it for the new body.
        passthrough_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() != "content-length"
        }
        return JSONResponse(
            content=wrapped,
            status_code=response.status_code,
            headers=passthrough_headers,
            media_type="application/json",
        )
