"""Execution Run State Machine implementation."""
from __future__ import annotations

from workflow_engine.errors import WorkflowEngineError
from workflow_engine.models.execution import ExecutionRun, RunStatus
from workflow_engine.ports import ExecutionRepository


class StateTransitionError(WorkflowEngineError):
    def __init__(self, run_id: str, from_state: RunStatus, to_state: RunStatus):
        super().__init__(
            f"Invalid state transition for run {run_id}: {from_state} -> {to_state}",
            code="STATE_TRANSITION"
        )


class StateMachine:
    """Manages valid RunStatus transitions for ExecutionRuns."""

    _VALID_TRANSITIONS = {
        RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED},
        RunStatus.RUNNING: {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.WAITING_HUMAN},
        RunStatus.WAITING_HUMAN: {RunStatus.RUNNING, RunStatus.CANCELLED},
        RunStatus.SUCCESS: set(),
        RunStatus.FAILED: set(),
        RunStatus.CANCELLED: set(),
    }

    @classmethod
    async def transition_run(
        cls, repo: ExecutionRepository, tenant_id: str, run_id: str, new_status: RunStatus
    ) -> ExecutionRun:
        """
        Transition an overall ExecutionRun status safely.

        Raises StateTransitionError if the move is fundamentally outlawed.
        Delegates the optimistic locking / persistence to the ExecutionRepository.
        """
        # Fetch the current state
        # Depending on concurrency needs, a lock could be taken out or repository handles it via CAS.
        run = await repo.get(tenant_id, run_id)
        if not run:
            raise WorkflowEngineError(f"Run {run_id} not found", code="RUN_NOT_FOUND")

        from_state = run.status

        # If it's the exact same state, no-op update
        if from_state == new_status:
            return run

        allowed = cls._VALID_TRANSITIONS.get(from_state, set())
        if new_status not in allowed:
            raise StateTransitionError(run_id, from_state, new_status)

        # Transition is allowed, update
        run.status = new_status
        run = await repo.update_state(tenant_id, run_id, run)
        return run

    @classmethod
    async def transition_node(
        cls, repo: ExecutionRepository, tenant_id: str, run_id: str, node_id: str, new_status: RunStatus, **kwargs: dict
    ) -> None:
        """
        Atomically update the state of a single NodeExecutionState.

        Uses a targeted $set on node_states.<node_id> to avoid overwriting
        sibling node states in parallel execution scenarios.
        """
        from workflow_engine.models.execution import NodeExecutionState
        from datetime import datetime, timezone

        node_state = NodeExecutionState(status=new_status)
        if "outputs" in kwargs:
            node_state.outputs = kwargs["outputs"]
        if "error" in kwargs:
            node_state.error = str(kwargs["error"])
        if new_status == RunStatus.RUNNING:
            node_state.started_at = datetime.now(timezone.utc)
        elif new_status in (RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED):
            node_state.ended_at = datetime.now(timezone.utc)

        await repo.update_node_state(tenant_id, run_id, node_id, node_state)
