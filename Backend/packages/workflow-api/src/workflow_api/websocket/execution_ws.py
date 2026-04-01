"""
WebSocket endpoint — streams NodeExecutionState updates to clients.

WS /ws/executions/{run_id}

Protocol:
  Client connects with an auth token as query param:
      ws://host/ws/executions/<run_id>?token=<jwt>

  Server sends JSON messages as node execution state changes:
      {"type": "node_state", "node_id": "...", "status": "running", "ts": "..."}
      {"type": "run_complete", "status": "succeeded", "ts": "..."}
      {"type": "error", "detail": "..."}

  Connection closes when:
    - The run reaches a terminal state (succeeded / failed / cancelled)
    - Client disconnects
    - Auth fails (close code 4001)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

logger = logging.getLogger("dk.api.ws")
router = APIRouter(tags=["WebSocket"])

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}
POLL_INTERVAL_SECONDS = 0.2   # 200ms polling → well within 500ms AC requirement


@router.websocket("/ws/executions/{run_id}")
async def execution_ws(ws: WebSocket, run_id: str):
    """
    Stream NodeExecutionState updates for a given run_id.

    AC: Emits state update within 500ms of node completion.
        Achieved via POLL_INTERVAL_SECONDS = 0.2s polling.
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

    # ── Stream loop ────────────────────────────────────────────────────────
    execution_service = ws.app.state.execution_service
    seen_node_ids: set[str] = set()

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

            # Emit node state updates for any newly-completed nodes
            nodes = run.get("nodes", [])
            for node in nodes:
                node_key = f"{node.get('node_id')}:{node.get('status')}"
                if node_key not in seen_node_ids:
                    seen_node_ids.add(node_key)
                    await ws.send_text(json.dumps({
                        "type": "node_state",
                        "node_id": node.get("node_id"),
                        "status": node.get("status"),
                        "ts": datetime.now(tz=timezone.utc).isoformat(),
                    }))

            # Check terminal condition
            if run.get("status") in TERMINAL_STATES:
                await ws.send_text(json.dumps({
                    "type": "run_complete",
                    "status": run["status"],
                    "ts": datetime.now(tz=timezone.utc).isoformat(),
                }))
                break

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: run_id={run_id}")
    finally:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close()
