from enum import StrEnum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Any

from pydantic import BaseModel

class ConversationPhase(StrEnum):
    GATHERING = "GATHERING"
    CLARIFYING = "CLARIFYING"
    FINALIZING = "FINALIZING"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"

@dataclass
class ProcessingStep:
    description: str
    suggested_node_type: str | None = None
    config_hints: dict[str, Any] = field(default_factory=dict)

@dataclass
class RequirementSpec:
    goal: str | None = None
    trigger_type: str | None = None      # manual | scheduled | webhook
    trigger_config: dict[str, Any] = field(default_factory=dict)
    input_sources: list[str] = field(default_factory=list)
    processing_steps: list[ProcessingStep] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    output_format: str | None = None
    constraints: dict[str, Any] = field(default_factory=dict)

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.goal:
            missing.append("goal")
        if not self.trigger_type:
            missing.append("trigger_type")
        if not self.processing_steps:
            missing.append("processing_steps")
        if not self.output_format:
            missing.append("output_format")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    ts: datetime

class ChatSession(BaseModel):
    session_id: str
    tenant_id: str
    user_id: str
    phase: ConversationPhase
    messages: list[ChatMessage]
    requirement_spec: RequirementSpec | None
    generated_workflow_id: str | None
    clarification_round: int
    created_at: datetime
    updated_at: datetime
