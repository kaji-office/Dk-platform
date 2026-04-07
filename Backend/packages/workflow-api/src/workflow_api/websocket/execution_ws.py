"""
WebSocket endpoint — streams NodeExecutionState updates to clients via Redis PubSub.

WS /ws/executions/{run_id}

Protocol:
  Client connects with an auth token as query param:
      ws://host/ws/executions/<run_id>?token=<jwt>

  On connect, a snapshot of all already-completed node states is sent immediately
  (catch-up for clients that connect mid-execution).

  Server then streams JSON messages as state changes are published by the orchestrator:
      {"type": "node_state",        "node_id": "...", "status": "running",   "ts": "..."}
      {"type": "run_complete",      "status": "succeeded",                   "ts": "..."}
      {"type": "run_waiting_human", "node_id": "...",                        "ts": "..."}
      {"type": "snapshot",          "nodes": [...], "run_status": "...",     "ts": "..."}
      {"type": "error",             "detail": "..."}

  Connection closes when:
    - The run reaches a terminal state (succeeded / failed / cancelled)
    - Client disconnects
    - Auth fails (close code 4001)
    - Redis PubSub is unavailable (falls back to polling mode)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("dk.api.ws")
router = APIRouter(tags=["WebSocket"])

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "timed_out"}
# Fallback poll interval used when Redis PubSub is unavailable
_FALLBACK_POLL_INTERVAL = 0.5


@router.websocket("/ws/executions/{run_id}")
async def execution_ws(ws: WebSocket, run_id: str):
    """
    Stream NodeExecutionState updates for a given run_id via Redis PubSub.

    AC: Emits state update within 500ms of node completion.
        Achieved via Redis PubSub — latency is network-bound, typically <10ms.

    Catch-up: On initial connection, a snapshot of all completed node states is
    emitted before subscribing, so late-joiners don't miss earlier events.
    """
    await ws.accept()

    # ── Authenticate ───────────────────────────────────────────────────────
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Authentication required")
        return

    auth_service = ws.app.state.auth_service
    try:
        user = await auth_service.verify_token(token)
        tenant_id = user["tenant_id"]
    except Exception:
        await ws.close(code=4001, reason="Invalid token")
        return

    execution_service = ws.app.state.execution_service

    # ── Snapshot: emit all already-completed node states ───────────────────
    try:
        run = await execution_service.get(tenant_id, run_id)
        if run is None:
            await ws.send_text(json.dumps({"type": "error", "detail": "Run not found"}))
            await ws.close()
            return

        nodes_snapshot = run.get("nodes", [])
        await ws.send_text(json.dumps({
            "type": "snapshot",
            "nodes": nodes_snapshot,
            "run_status": run.get("status"),
            "ts": datetime.now(tz=timezone.utc).isoformat(),
        }))

        # If already terminal, close immediately
        if run.get("status") in TERMINAL_STATUSES:
            await ws.send_text(json.dumps({
                "type": "run_complete",
                "status": run["status"],
                "ts": datetime.now(tz=timezone.utc).isoformat(),
            }))
            await ws.close()
            return

    except Exception as exc:
        await ws.send_text(json.dumps({"type": "error", "detail": str(exc)}))
        await ws.close()
        return

    # ── PubSub subscription ────────────────────────────────────────────────
    redis_client = getattr(ws.app.state, "redis_client", None)

    if redis_client is not None:
        await _stream_via_pubsub(ws, run_id, tenant_id, execution_service, redis_client)
    else:
        # Graceful degradation: fall back to polling if Redis is not wired
        logger.warning("Redis not available for WS PubSub — falling back to polling for run %s", run_id)
        await _stream_via_polling(ws, run_id, tenant_id, execution_service)


async def _stream_via_pubsub(
    ws: WebSocket,
    run_id: str,
    tenant_id: str,
    execution_service,
    redis_client,
) -> None:
    """Subscribe to run:{run_id}:events and forward messages to the WebSocket client."""
    channel = f"run:{run_id}:events"
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe(channel)

        while True:
            if ws.client_state != WebSocketState.CONNECTED:
                break

            # get_message is non-blocking; we sleep briefly to avoid busy-loop
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
            except asyncio.TimeoutError:
                message = None

            if message is not None and message.get("type") == "message":
                raw = message.get("data", "")
                try:
                    event = json.loads(raw)
                except Exception:
                    continue

                try:
                    await ws.send_text(raw if isinstance(raw, str) else json.dumps(event))
                except Exception:
                    break

                # Close after terminal event
                event_type = event.get("type", "")
                if event_type == "run_complete":
                    break

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected: run_id=%s", run_id)
    except Exception as exc:
        logger.error("PubSub stream error for run %s: %s", run_id, exc)
        try:
            await ws.send_text(json.dumps({"type": "error", "detail": "Stream interrupted"}))
        except Exception:
            pass
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            pass
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close()


async def _stream_via_polling(
    ws: WebSocket,
    run_id: str,
    tenant_id: str,
    execution_service,
) -> None:
    """Fallback polling loop (used when Redis PubSub is not available)."""
    seen_node_keys: set[str] = set()

    try:
        while True:
            if ws.client_state != WebSocketState.CONNECTED:
                break

            try:
                run = await execution_service.get(tenant_id, run_id)
            except Exception as exc:
                await ws.send_text(json.dumps({"type": "error", "detail": str(exc)}))
                break

            if run is None:
                await ws.send_text(json.dumps({"type": "error", "detail": "Run not found"}))
                break

            for node in run.get("nodes", []):
                node_key = f"{node.get('node_id')}:{node.get('status')}"
                if node_key not in seen_node_keys:
                    seen_node_keys.add(node_key)
                    await ws.send_text(json.dumps({
                        "type": "node_state",
                        "node_id": node.get("node_id"),
                        "status": node.get("status"),
                        "ts": datetime.now(tz=timezone.utc).isoformat(),
                    }))

            if run.get("status") in TERMINAL_STATUSES:
                await ws.send_text(json.dumps({
                    "type": "run_complete",
                    "status": run["status"],
                    "ts": datetime.now(tz=timezone.utc).isoformat(),
                }))
                break

            await asyncio.sleep(_FALLBACK_POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected (poll): run_id=%s", run_id)
    finally:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close()
