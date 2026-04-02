import asyncio
import contextlib
import json
import logging
from typing import Any
import uuid

from fastapi import APIRouter, Query, Request, status, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite
from workflow_engine.chat.models import ConversationPhase, RequirementSpec, ChatSession
from workflow_engine.chat.orchestrator import ChatOrchestrator
from workflow_engine.models import WorkflowDefinition

router = APIRouter(prefix="/chat/sessions", tags=["Chat"])

class CreateMessageRequest(BaseModel):
    content: str
    
class UpdateWorkflowRequest(BaseModel):
    workflow: WorkflowDefinition

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_session(user: CurrentUser, tenant_id: TenantId, request: Request) -> ChatSession:
    """Create a new chat session."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    try:
        session = await orch.repo.create_session(tenant_id, user["id"])
        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("")
async def list_sessions(user: CurrentUser, tenant_id: TenantId, request: Request) -> dict[str, Any]:
    """List tenant sessions."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    sessions = await orch.repo.list_sessions(tenant_id)
    return {"sessions": sessions}

@router.get("/{session_id}")
async def get_session(session_id: str, user: CurrentUser, tenant_id: TenantId, request: Request) -> ChatSession:
    """Full session + history."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    session = await orch.repo.get_session(session_id, tenant_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/message")
async def send_message(session_id: str, body: CreateMessageRequest, user: CurrentUser, tenant_id: TenantId, request: Request) -> dict[str, Any]:
    """Send message, get reply."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    try:
        res = await orch.process_message(session_id, tenant_id, body.content)
        import dataclasses
        return dataclasses.asdict(res)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{session_id}/generate")
async def force_generate(session_id: str, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict[str, Any] = RequireWrite) -> dict[str, Any]:
    """Force DAG generation (EDITOR role)."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    try:
        # Fetch session
        session = await orch.repo.get_session(session_id, tenant_id)
        if not session or not session.requirement_spec:
            raise HTTPException(status_code=400, detail="Cannot generate DAG without requirements.")
            
        await orch.repo.update_phase(session_id, ConversationPhase.GENERATING)
        
        # We manually invoke the generator
        workflow = await orch.generator.generate(session.requirement_spec)
        from workflow_engine.chat.workflow_layout import NodeUIConfigFactory, WorkflowLayoutEngine
        from workflow_engine.graph.builder import GraphBuilder
        
        for node in workflow.nodes.values():
            ui_conf = NodeUIConfigFactory.for_type(node.type)
            if "ui_config" not in node.config:
                node.config["ui_config"] = ui_conf.model_dump()
                
        workflow = WorkflowLayoutEngine.auto_layout(workflow)
        workflow.ui_metadata["chat_session_id"] = session_id
        
        GraphBuilder.validate(workflow)
        saved_wf = await orch.workflow_repo.create(tenant_id, workflow)
        
        await orch.repo.update_phase(session_id, ConversationPhase.COMPLETE)
        if hasattr(orch.repo, "record_workflow_id"):
            await orch.repo.record_workflow_id(session_id, saved_wf.id)
            
        return {"workflow_id": saved_wf.id, "workflow": saved_wf.model_dump()}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{session_id}/workflow")
async def submit_workflow_edits(session_id: str, body: UpdateWorkflowRequest, user: CurrentUser, tenant_id: TenantId, request: Request, _: dict[str, Any] = RequireWrite) -> dict[str, Any]:
    """Submit workflow edits."""
    orch: ChatOrchestrator = request.app.state.chat_orchestrator
    res = await orch.validate_workflow_update(session_id, tenant_id, body.workflow)
    import dataclasses
    return dataclasses.asdict(res)

@router.websocket("/ws/chat/{session_id}")
async def stream_chat(
    websocket: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
) -> None:
    """
    WebSocket chat streaming backed by Redis PubSub.

    Connect: wss://.../api/v1/chat/sessions/ws/chat/{session_id}?token=<jwt>

    Client sends:  {"type": "message", "content": "..."}
    Server emits:
        {"type": "status",   "phase": "PROCESSING"}
        {"type": "phase",    "phase": "CLARIFYING"|"GENERATING"}
        {"type": "response", "phase": "COMPLETE", "message": "...", "workflow_id": "..."}
    """
    # Authenticate via query param — browsers can't set Authorization headers on WebSocket.
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    try:
        user = await websocket.app.state.auth_service.verify_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    tenant_id: str = user["tenant_id"]
    orch: ChatOrchestrator = websocket.app.state.chat_orchestrator
    redis_client = websocket.app.state.redis_client
    channel = f"chat:{session_id}:events"

    await websocket.accept()

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)

    async def _publisher(sid: str, event: dict) -> None:
        try:
            await redis_client.publish(f"chat:{sid}:events", json.dumps(event))
        except Exception as exc:
            logger.warning("chat publish error: %s", exc)

    async def _listen_pubsub() -> None:
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                try:
                    await websocket.send_text(msg["data"])
                except Exception:
                    return

    async def _handle_client() -> None:
        try:
            async for raw in websocket.iter_text():
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "message" and data.get("content"):
                    asyncio.create_task(
                        orch.process_message(
                            session_id, tenant_id, data["content"], publish=_publisher
                        )
                    )
        except WebSocketDisconnect:
            pass

    pubsub_task = asyncio.create_task(_listen_pubsub())
    client_task = asyncio.create_task(_handle_client())

    try:
        await asyncio.wait({pubsub_task, client_task}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        pubsub_task.cancel()
        client_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pubsub_task
        with contextlib.suppress(asyncio.CancelledError):
            await client_task
        with contextlib.suppress(Exception):
            await pubsub.aclose()
        with contextlib.suppress(Exception):
            await websocket.close(code=1000)
