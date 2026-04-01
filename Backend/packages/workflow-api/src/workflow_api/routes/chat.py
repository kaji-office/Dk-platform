import asyncio
from typing import Any
import uuid

from fastapi import APIRouter, Request, status, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from workflow_api.dependencies import CurrentUser, TenantId, RequireWrite
from workflow_engine.chat.models import ConversationPhase, RequirementSpec, ChatSession
from workflow_engine.chat.orchestrator import ChatOrchestrator
from workflow_engine.models import WorkflowDefinition

router = APIRouter(prefix="/v1/chat/sessions", tags=["Chat"])

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
async def stream_chat(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket streaming.
    In a fully event-driven architecture, this would subscribe to a Redis PubSub channel.
    Here we mock the connection emitting token patterns.
    """
    await websocket.accept()
    try:
        # A true implementation subscribes to LLM tokens. We emit a dummy stream payload.
        await websocket.send_json({"type": "token", "content": "Connected."})
        while True:
            # Keep open
            data = await websocket.receive_text()
            if data == "close":
                break
            await websocket.send_json({"type": "token", "content": f"ACK {data}"})
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close(code=1000)
        except Exception:
            pass
