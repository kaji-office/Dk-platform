"""
P9-T-10 — Idempotency key duplicate-trigger test.

Verifies that:
1. Two trigger requests with the same Idempotency-Key return the same run_id
2. Only one execution run is created (not two)
3. Two requests with different keys create two different runs
4. Requests without a key always create a new run
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from workflow_api.app import create_app


def _build_app():
    """Build test app with tracking execution service."""
    trigger_calls: list[dict] = []

    async def _track_trigger(*args, **kwargs):
        call_num = len(trigger_calls)
        result = {"run_id": f"run-{call_num:04d}"}
        trigger_calls.append(result)
        return result

    auth_svc = AsyncMock()
    auth_svc.verify_token.return_value = {"id": "u1", "tenant_id": "t1", "role": "ADMIN"}

    wf_svc = AsyncMock()
    wf_svc.get.return_value = {"id": "wf-1", "name": "Test", "is_active": True}

    exec_svc = AsyncMock()
    exec_svc.trigger.side_effect = _track_trigger
    exec_svc.list.return_value = []

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
    app.state.limiter.reset()
    app._trigger_calls = trigger_calls  # expose for assertions
    return app


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_same_run_id():
    """
    Two POST requests with the same Idempotency-Key must return identical run_id.
    The execution service should only be called once (second request hits cache).
    """
    app = _build_app()

    # Provide a Redis-like mock for idempotency key storage
    redis_mock = AsyncMock()
    # First call: key not in cache; second call: key IS in cache
    import json
    cached_value = None

    async def redis_get(key):
        return cached_value

    async def redis_setex(key, ttl, value):
        nonlocal cached_value
        cached_value = value

    redis_mock.get.side_effect = redis_get
    redis_mock.setex.side_effect = redis_setex
    app.state.redis_client = redis_mock

    headers = {
        "Authorization": "Bearer tok",
        "Idempotency-Key": "key-abc-123",
        "Content-Type": "application/json",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers=headers,
        )
        resp2 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers=headers,
        )

    assert resp1.status_code in (200, 202), f"First trigger failed: {resp1.status_code} {resp1.text}"
    assert resp2.status_code in (200, 202), f"Second trigger failed: {resp2.status_code} {resp2.text}"

    run_id_1 = (resp1.json().get("data") or resp1.json()).get("run_id")
    run_id_2 = (resp2.json().get("data") or resp2.json()).get("run_id")

    assert run_id_1 is not None, f"No run_id in first response: {resp1.json()}"
    assert run_id_2 is not None, f"No run_id in second response: {resp2.json()}"
    assert run_id_1 == run_id_2, (
        f"Expected same run_id for duplicate idempotency key, "
        f"got {run_id_1} and {run_id_2}"
    )


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_different_runs():
    """
    Two POST requests with different Idempotency-Keys must produce different run_ids.
    """
    app = _build_app()

    redis_mock = AsyncMock()
    cache_store: dict[str, str] = {}

    async def redis_get(key):
        return cache_store.get(key)

    async def redis_setex(key, ttl, value):
        cache_store[key] = value

    redis_mock.get.side_effect = redis_get
    redis_mock.setex.side_effect = redis_setex
    app.state.redis_client = redis_mock

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers={
                "Authorization": "Bearer tok",
                "Idempotency-Key": "key-aaa",
            },
        )
        resp2 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers={
                "Authorization": "Bearer tok",
                "Idempotency-Key": "key-bbb",
            },
        )

    assert resp1.status_code in (200, 202)
    assert resp2.status_code in (200, 202)

    run_id_1 = (resp1.json().get("data") or resp1.json()).get("run_id")
    run_id_2 = (resp2.json().get("data") or resp2.json()).get("run_id")

    assert run_id_1 != run_id_2, (
        f"Different idempotency keys should produce different run_ids, "
        f"got {run_id_1} and {run_id_2}"
    )


@pytest.mark.asyncio
async def test_no_idempotency_key_always_creates_new_run():
    """
    Requests without an Idempotency-Key header always create a new run.
    Two identical requests without a key produce different run_ids.
    """
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers={"Authorization": "Bearer tok"},
        )
        resp2 = await client.post(
            "/api/v1/workflows/wf-1/trigger",
            json={"input_data": {}},
            headers={"Authorization": "Bearer tok"},
        )

    assert resp1.status_code in (200, 202)
    assert resp2.status_code in (200, 202)

    run_id_1 = (resp1.json().get("data") or resp1.json()).get("run_id")
    run_id_2 = (resp2.json().get("data") or resp2.json()).get("run_id")

    # Both requests should have created runs (might be same if mocked consistently,
    # but the service should have been called twice)
    assert app.state.execution_service.trigger.call_count == 2, (
        "Expected trigger to be called twice (no idempotency key)"
    )
