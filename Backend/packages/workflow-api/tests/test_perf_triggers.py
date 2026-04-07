"""
P9-T-11 — Performance test: 100 concurrent trigger requests.

Verifies:
1. 100 concurrent POST /workflows/{id}/trigger requests all succeed (200 or 202)
2. All requests complete within a 10-second wall-clock deadline
3. Each response contains a unique run_id (no deduplication when no idempotency key)
4. The execution service is called exactly 100 times
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from slowapi import Limiter
from slowapi.util import get_remote_address

from workflow_api.app import create_app

_CONCURRENCY = 100
_WALL_CLOCK_LIMIT_SECONDS = 10.0


def _build_app():
    counter = {"n": 0}

    async def _trigger(*args, **kwargs):
        counter["n"] += 1
        return {"run_id": f"run-{counter['n']:06d}", "status": "QUEUED"}

    auth_svc = AsyncMock()
    auth_svc.verify_token.return_value = {"id": "u1", "tenant_id": "t1", "role": "ADMIN"}

    wf_svc = AsyncMock()
    wf_svc.get.return_value = {"id": "wf-perf", "name": "Perf WF", "is_active": True}

    exec_svc = AsyncMock()
    exec_svc.trigger.side_effect = _trigger

    services = {
        "auth_service": auth_svc,
        "user_service": AsyncMock(),
        "workflow_service": wf_svc,
        "execution_service": exec_svc,
        "webhook_service": AsyncMock(),
        "audit_service": AsyncMock(),
        "billing_service": AsyncMock(),
        "schedule_service": AsyncMock(),
    }
    app = create_app(services=services)
    # Replace limiter with a no-limit version for perf testing
    app.state.limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["100000/minute"],
        storage_uri="memory://",
    )
    app._exec_svc = exec_svc
    return app


@pytest.mark.asyncio
async def test_100_concurrent_triggers_all_succeed():
    """
    Fire 100 concurrent trigger requests; all must return 2xx within the deadline.
    """
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        start = time.monotonic()
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/workflows/wf-perf/trigger",
                    json={"input_data": {}},
                    headers={"Authorization": "Bearer tok"},
                )
                for _ in range(_CONCURRENCY)
            ]
        )
        elapsed = time.monotonic() - start

    statuses = [r.status_code for r in responses]
    failures = [s for s in statuses if s not in (200, 202)]
    assert not failures, f"{len(failures)} requests failed: {set(failures)}"

    assert elapsed < _WALL_CLOCK_LIMIT_SECONDS, (
        f"100 concurrent triggers took {elapsed:.2f}s, expected <{_WALL_CLOCK_LIMIT_SECONDS}s"
    )


@pytest.mark.asyncio
async def test_100_concurrent_triggers_all_unique_run_ids():
    """
    Without idempotency keys, every trigger must return a distinct run_id.
    """
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    "/api/v1/workflows/wf-perf/trigger",
                    json={"input_data": {}},
                    headers={"Authorization": "Bearer tok"},
                )
                for _ in range(_CONCURRENCY)
            ]
        )

    run_ids = [
        (r.json().get("data") or r.json()).get("run_id")
        for r in responses
        if r.status_code in (200, 202)
    ]
    assert len(run_ids) == _CONCURRENCY, f"Expected {_CONCURRENCY} run_ids, got {len(run_ids)}"
    assert len(set(run_ids)) == _CONCURRENCY, (
        f"Expected all run_ids to be unique; got {_CONCURRENCY - len(set(run_ids))} duplicates"
    )


@pytest.mark.asyncio
async def test_100_concurrent_triggers_service_called_100_times():
    """
    The execution service must be called exactly 100 times (no short-circuiting).
    """
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await asyncio.gather(
            *[
                client.post(
                    "/api/v1/workflows/wf-perf/trigger",
                    json={"input_data": {}},
                    headers={"Authorization": "Bearer tok"},
                )
                for _ in range(_CONCURRENCY)
            ]
        )

    call_count = app._exec_svc.trigger.call_count
    assert call_count == _CONCURRENCY, (
        f"Expected trigger called {_CONCURRENCY} times, got {call_count}"
    )
