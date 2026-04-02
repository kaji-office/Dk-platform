from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import uuid
import logging
from datetime import datetime, timezone

from workflow_engine.chat.models import ConversationPhase, RequirementSpec, ChatSession, ChatMessage
from workflow_engine.chat.requirement_extractor import RequirementExtractor
from workflow_engine.chat.clarification_engine import ClarificationEngine
from workflow_engine.chat.dag_generator import DAGGeneratorService
from workflow_engine.chat.workflow_layout import WorkflowLayoutEngine, NodeUIConfigFactory
from workflow_engine.ports import ConversationRepository, WorkflowRepository
from workflow_engine.models import WorkflowDefinition
from workflow_engine.errors import WorkflowValidationError
from workflow_engine.graph.builder import GraphBuilder

logger = logging.getLogger(__name__)

@dataclass
class ClarificationBlock:
    questions: list[str]

@dataclass
class ChatResponse:
    message: str                              # assistant reply text
    phase: ConversationPhase
    clarification: ClarificationBlock | None  # structured Qs when CLARIFYING
    requirement_spec: RequirementSpec | None
    workflow_preview: WorkflowDefinition | None  # with ui_config + ui_metadata
    workflow_id: str | None                   # set when COMPLETE

@dataclass
class WorkflowUpdateResponse:
    valid: bool
    workflow: WorkflowDefinition | None = None
    validation_errors: list[str] | None = None
    suggestions: list[str] | None = None

class ChatOrchestrator:
    def __init__(
        self,
        repo: ConversationRepository,
        workflow_repo: WorkflowRepository,
        extractor: RequirementExtractor,
        clarifier: ClarificationEngine,
        generator: DAGGeneratorService
    ):
        self.repo = repo
        self.workflow_repo = workflow_repo
        self.extractor = extractor
        self.clarifier = clarifier
        self.generator = generator

    async def process_message(
        self,
        session_id: str,
        tenant_id: str,
        user_message: str,
        publish: Callable[[str, dict], Awaitable[None]] | None = None,
    ) -> ChatResponse:
        async def _emit(event: dict) -> None:
            if publish:
                try:
                    await publish(session_id, event)
                except Exception as exc:
                    logger.debug(f"chat publish error: {exc}")

        session = await self.repo.get_session(session_id, tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # 1. Append User Msg
        msg_id_req = f"msg_{uuid.uuid4().hex}"
        req_msg = ChatMessage(id=msg_id_req, role="user", content=user_message, ts=datetime.now(timezone.utc))
        await self.repo.append_message(session_id, req_msg)
        session.messages.append(req_msg)

        await _emit({"type": "status", "phase": "PROCESSING"})

        if session.phase == ConversationPhase.COMPLETE:
            # Already complete, reply generic message. 
            # Could trigger regeneration if user wants edits, but typically they'd use explicit `force_generate` 
            # or `validate_workflow_update`. We will just return current state without DAG regeneration.
            return self._build_response(session, "Workflow is already completed.", None)

        # 2. Extract 
        spec = await self.extractor.extract(session.messages)
        await self.repo.update_spec(session_id, spec)
        session.requirement_spec = spec

        # 3. Clarification
        try:
            questions = await self.clarifier.get_questions(spec, session.clarification_round, session.messages)
        except Exception as e:
            logger.warning(f"Clarification maxed out or failed: {e}")
            questions = [] # Force proceed if failed

        if questions:
            await self.repo.update_phase(session_id, ConversationPhase.CLARIFYING)
            session.phase = ConversationPhase.CLARIFYING
            await _emit({"type": "phase", "phase": "CLARIFYING"})

            clarification_msg = "\n".join(f"- {q}" for q in questions)
            
            # Save Assistant Reply
            assistant_msg = ChatMessage(id=f"msg_{uuid.uuid4().hex}", role="assistant", content=clarification_msg, ts=datetime.now(timezone.utc))
            await self.repo.append_message(session_id, assistant_msg)
            
            return self._build_response(
                session,
                "I have a few questions to complete the workflow spec.",
                ClarificationBlock(questions=questions)
            )

        # 4. Phase -> FINALIZING/GENERATING
        await self.repo.update_phase(session_id, ConversationPhase.GENERATING)
        session.phase = ConversationPhase.GENERATING
        await _emit({"type": "phase", "phase": "GENERATING"})

        # 5. Generate DAG
        try:
            workflow = await self.generator.generate(spec)
        except Exception as e:
            await self.repo.update_phase(session_id, ConversationPhase.GATHERING) # Fall back
            assistant_msg = ChatMessage(id=f"msg_{uuid.uuid4().hex}", role="assistant", content=f"Failed to generate workflow constraint: {e}", ts=datetime.now(timezone.utc))
            await self.repo.append_message(session_id, assistant_msg)
            return self._build_response(session, f"I couldn't generate the DAG: {e}", None)

        # 6. UI Config & Layout
        # Add Node UI metadata based off Factory directly onto each node.config
        for node in workflow.nodes.values():
            ui_conf = NodeUIConfigFactory.for_type(node.type)
            if "ui_config" not in node.config:
                node.config["ui_config"] = ui_conf.model_dump()
                
        workflow = WorkflowLayoutEngine.auto_layout(workflow)
        workflow.ui_metadata["chat_session_id"] = session_id
        
        # 7. Validate 
        try:
            GraphBuilder.validate(workflow)
        except WorkflowValidationError as e:
            # Fall back to regenerating or throwing error
            assistant_msg = ChatMessage(id=f"msg_{uuid.uuid4().hex}", role="assistant", content=f"Generated workflow had validation issues: {e}", ts=datetime.now(timezone.utc))
            await self.repo.append_message(session_id, assistant_msg)
            return self._build_response(session, "Generated DAG was invalid structure.", None)

        # 8. Create into Workflow Repo
        saved_wf = await self.workflow_repo.create(tenant_id, workflow)
        
        await self.repo.update_phase(session_id, ConversationPhase.COMPLETE)
        if hasattr(self.repo, "record_workflow_id"):
            await self.repo.record_workflow_id(session_id, saved_wf.id)
            
        session.phase = ConversationPhase.COMPLETE
        session.generated_workflow_id = saved_wf.id
        
        assistant_msg = ChatMessage(id=f"msg_{uuid.uuid4().hex}", role="assistant", content=f"Your workflow '{saved_wf.name}' has been successfully generated!", ts=datetime.now(timezone.utc))
        await self.repo.append_message(session_id, assistant_msg)
        await _emit({
            "type": "response",
            "phase": "COMPLETE",
            "message": assistant_msg.content,
            "workflow_id": saved_wf.id,
        })

        return self._build_response(
            session,
            assistant_msg.content,
            None,
            saved_wf
        )

    def _build_response(self, session: ChatSession, message: str, clarification: ClarificationBlock | None, preview: WorkflowDefinition | None = None) -> ChatResponse:
        return ChatResponse(
            message=message,
            phase=session.phase,
            clarification=clarification,
            requirement_spec=session.requirement_spec,
            workflow_preview=preview,
            workflow_id=session.generated_workflow_id
        )

    async def validate_workflow_update(self, session_id: str, tenant_id: str, update: WorkflowDefinition) -> WorkflowUpdateResponse:
        try:
            GraphBuilder.validate(update)
            # Valid -> Persist to DB directly through workflow_repo
            updated_wf = await self.workflow_repo.update(tenant_id, update.id, update)
            return WorkflowUpdateResponse(valid=True, workflow=updated_wf, suggestions=[])
            
        except WorkflowValidationError as e:
            return WorkflowUpdateResponse(valid=False, validation_errors=[str(e)])
