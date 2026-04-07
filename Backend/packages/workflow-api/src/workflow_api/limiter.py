"""
Rate-limiter singleton — extracted here to avoid circular imports.

app.py imports routes, routes import limiter → circular.
By placing limiter in its own module, both app.py and routes can
import from workflow_api.limiter without a cycle.
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _get_tenant_key(request: Request) -> str:
    """Rate-limit key: tenant_id from auth context, fallback to IP."""
    user = getattr(request.state, "user", None)
    if user and user.get("tenant_id"):
        return f"tenant:{user['tenant_id']}"
    return get_remote_address(request)


_redis_url = os.environ.get("REDIS_URL", "memory://")
limiter = Limiter(
    key_func=_get_tenant_key,
    default_limits=["60/minute"],
    storage_uri=_redis_url,
    # Fail open when the storage backend (Redis) is unavailable — allows requests through
    # rather than crashing with AttributeError: 'ConnectionError' has no attribute 'detail'
    swallow_errors=True,
)
