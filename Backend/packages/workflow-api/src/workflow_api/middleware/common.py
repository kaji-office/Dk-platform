"""
Middleware stack for the DK workflow-api.

Order (outermost → innermost):
  1. RequestIDMiddleware   — injects X-Request-ID into every request/response
  2. CORSMiddleware        — (added via FastAPI add_middleware in app.py)
  3. ResponseEnvelopeMiddleware — wraps 2xx JSON responses in {success, data, request_id}
"""
from __future__ import annotations

import contextvars
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import json

# Context variable — service code can call get_current_request_id() to retrieve
# the active request_id without needing a reference to the Request object.
_current_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "_current_request_id", default=""
)


def get_current_request_id() -> str:
    """Return the request_id for the current async context, or empty string."""
    return _current_request_id.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique X-Request-ID header into every request and response.
    Uses incoming value if already present (idempotent for upstream proxies).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Attach to request state and contextvars for downstream access
        request.state.request_id = request_id
        token = _current_request_id.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _current_request_id.reset(token)
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
    Large responses (>1MB) are streamed without buffering.
    """

    # Routes excluded from envelope wrapping
    SKIP_PATHS = {"/health", "/health/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}

    # Responses larger than this are passed through to avoid OOM on large exports
    MAX_BUFFER_BYTES = 1 * 1024 * 1024  # 1MB

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # For 429 Rate Limit Exceeded, ensure Retry-After is present
        if response.status_code == 429:
            response.headers["Retry-After"] = "60"

        # Skip non-JSON, errors, WebSocket upgrades, excluded paths, and large responses
        content_type = response.headers.get("content-type", "")
        content_length = int(response.headers.get("content-length", 0) or 0)
        if (
            request.url.path in self.SKIP_PATHS
            or response.status_code >= 400
            or "application/json" not in content_type
            or response.status_code == 101  # WebSocket upgrade
            or content_length > self.MAX_BUFFER_BYTES
        ):
            return response

        # Read and re-wrap the body — bail out if buffering exceeds limit
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
            if len(body) > self.MAX_BUFFER_BYTES:
                # Body is too large — pass through unmodified (cannot re-stream safely)
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=content_type,
                )

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
