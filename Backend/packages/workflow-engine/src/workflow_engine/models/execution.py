from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    WAITING_HUMAN = "WAITING_HUMAN"

class NodeExecutionState(BaseModel):
    status: RunStatus = Field(default=RunStatus.QUEUED)
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)

class ExecutionRun(BaseModel):
    run_id: str = Field(..., description="Execution run ID")
    workflow_id: str = Field(..., description="Workflow ID")
    tenant_id: str = Field(..., description="Tenant ID executing the run")
    status: RunStatus = Field(default=RunStatus.QUEUED)
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    node_states: dict[str, NodeExecutionState] = Field(default_factory=dict)
    error: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
