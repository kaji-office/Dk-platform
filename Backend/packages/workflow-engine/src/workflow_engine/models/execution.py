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
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list, description="Structured log lines emitted during node execution")

class ExecutionRun(BaseModel):
    run_id: str = Field(..., description="Execution run ID")
    workflow_id: str = Field(..., description="Workflow ID")
    tenant_id: str = Field(..., description="Tenant ID executing the run")
    status: RunStatus = Field(default=RunStatus.QUEUED)
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    node_states: dict[str, NodeExecutionState] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    celery_task_id: str | None = Field(default=None, description="Celery AsyncResult task ID for cancellation")
    retry_of: str | None = Field(default=None, description="Original run_id this run is a retry of")
