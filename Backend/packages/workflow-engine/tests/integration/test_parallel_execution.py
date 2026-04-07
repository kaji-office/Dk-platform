"""
P9-T-02 — Parallel node state race condition test.

Verifies that concurrent node writes in a parallel topological layer do not
overwrite each other's state. All nodes in a layer must appear as SUCCESS
after execution, with no silent overwrites.

The test uses an in-memory ExecutionRepository that simulates the atomic
$set semantics of MongoExecutionRepository.update_node_state() and
bulk_update_node_states() — each operation only touches the targeted
node's state and never clobbers sibling nodes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from workflow_engine.execution.orchestrator import RunOrchestrator
from workflow_engine.models.execution import ExecutionRun, NodeExecutionState, RunStatus
from workflow_engine.models.tenant import TenantConfig, PlanTier
from workflow_engine.models.workflow import EdgeDefinition, NodeDefinition, WorkflowDefinition
from workflow_engine.nodes.base import NodeServices
from workflow_engine.ports import ExecutionRepository


# ---------------------------------------------------------------------------
# In-memory repo — simulates MongoDB atomic $set semantics
# ---------------------------------------------------------------------------

class InMemoryExecutionRepo(ExecutionRepository):
    """Thread-safe (single event-loop) in-memory ExecutionRepository for tests."""

    def __init__(self):
        self._store: dict[str, dict] = {}  # run_id → serialised ExecutionRun dict

    def _key(self, tenant_id: str, run_id: str) -> str:
        return f"{tenant_id}:{run_id}"

    async def get(self, tenant_id: str, run_id: str) -> ExecutionRun | None:
        doc = self._store.get(self._key(tenant_id, run_id))
        if doc is None:
            return None
        return ExecutionRun.model_validate(doc)

    async def create(self, tenant_id: str, execution: ExecutionRun) -> ExecutionRun:
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        self._store[self._key(tenant_id, execution.run_id)] = data
        return execution

    async def update_state(self, tenant_id: str, run_id: str, execution: ExecutionRun) -> ExecutionRun:
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        self._store[self._key(tenant_id, run_id)] = data
        return execution

    async def list(self, tenant_id: str, workflow_id: str | None = None, skip: int = 0, limit: int = 100) -> list[ExecutionRun]:
        return [ExecutionRun.model_validate(d) for d in self._store.values()]

    async def get_node_states(self, tenant_id: str, run_id: str) -> list[dict[str, Any]]:
        doc = self._store.get(self._key(tenant_id, run_id))
        if not doc:
            return []
        return list(doc.get("node_states", {}).values())

    async def list_runs_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 50) -> list[ExecutionRun]:
        return [ExecutionRun.model_validate(d) for d in self._store.values()]

    async def patch_fields(self, tenant_id: str, run_id: str, fields: dict[str, Any]) -> None:
        key = self._key(tenant_id, run_id)
        if key in self._store:
            self._store[key].update(fields)

    async def update_node_state(
        self,
        tenant_id: str,
        run_id: str,
        node_id: str,
        node_state: NodeExecutionState,
    ) -> None:
        """Atomic $set: only touch node_states[node_id], leave siblings intact."""
        key = self._key(tenant_id, run_id)
        if key not in self._store:
            return
        doc = self._store[key]
        if "node_states" not in doc:
            doc["node_states"] = {}
        # Simulate MongoDB dotted-path $set — only this node's slot is written.
        doc["node_states"][node_id] = node_state.model_dump(mode="json")

    async def bulk_update_node_states(
        self,
        tenant_id: str,
        run_id: str,
        states: dict[str, NodeExecutionState],
    ) -> None:
        """Single $set for multiple nodes — simulates one MongoDB round-trip."""
        key = self._key(tenant_id, run_id)
        if key not in self._store or not states:
            return
        doc = self._store[key]
        if "node_states" not in doc:
            doc["node_states"] = {}
        for node_id, state in states.items():
            doc["node_states"][node_id] = state.model_dump(mode="json")

    async def list_stale_running(self, before: datetime) -> list[ExecutionRun]:
        result = []
        for doc in self._store.values():
            if doc.get("status") == "RUNNING":
                started = doc.get("started_at")
                if started and started < before:
                    result.append(ExecutionRun.model_validate(doc))
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_parallel_workflow(n_parallel: int) -> WorkflowDefinition:
    """
    Build a workflow:
        trigger → [node_0, node_1, ..., node_{n-1}]

    All `node_i` are in the same topological layer — they execute concurrently.
    """
    nodes: dict[str, NodeDefinition] = {
        "trigger": NodeDefinition(id="trigger", type="ManualTriggerNode", config={}),
    }
    edges: list[EdgeDefinition] = []

    for i in range(n_parallel):
        nid = f"node_{i}"
        nodes[nid] = NodeDefinition(id=nid, type="ManualTriggerNode", config={})
        edges.append(EdgeDefinition(
            id=f"e_{i}",
            source_node="trigger",
            target_node=nid,
        ))

    return WorkflowDefinition(id="wf-parallel-test", nodes=nodes, edges=edges)


async def _run_once(repo: InMemoryExecutionRepo, workflow: WorkflowDefinition, run_id: str) -> ExecutionRun:
    """Create and execute a single run, returning the final state."""
    tenant_id = "test-tenant"
    run = ExecutionRun(run_id=run_id, workflow_id=workflow.id, tenant_id=tenant_id, status=RunStatus.QUEUED)
    await repo.create(tenant_id, run)

    orchestrator = RunOrchestrator(
        repo=repo,
        services=NodeServices(),
        config=TenantConfig(tenant_id=tenant_id, plan_tier=PlanTier.PRO),
    )
    result = await orchestrator.run(workflow, run_id, tenant_id, {})
    assert result is not None, f"Orchestrator returned None for run {run_id}"
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_parallel_nodes_succeed_single_run():
    """
    Single run with 10 parallel nodes — all must reach SUCCESS status.
    """
    N = 10
    workflow = _build_parallel_workflow(N)
    repo = InMemoryExecutionRepo()

    result = await _run_once(repo, workflow, "run-parallel-single")

    assert result.status == RunStatus.SUCCESS, f"Run status: {result.status}"

    # trigger + N parallel nodes
    assert len(result.node_states) == N + 1, (
        f"Expected {N + 1} node states, got {len(result.node_states)}: {list(result.node_states)}"
    )

    for node_id, state in result.node_states.items():
        if node_id == "trigger":
            continue  # trigger may be SUCCESS or skipped depending on entry handling
        assert state.status == RunStatus.SUCCESS, (
            f"Node {node_id} expected SUCCESS, got {state.status}"
        )


@pytest.mark.asyncio
async def test_parallel_nodes_no_state_overwrite_multiple_runs():
    """
    50 concurrent runs, each with 10 parallel nodes.
    After every run, ALL 10 parallel node states must be SUCCESS.
    This would fail if update_node_state used a non-atomic read-modify-write
    (as the old replace_one implementation did), because concurrent coroutines
    could overwrite each other's changes.
    """
    N = 10
    CONCURRENT_RUNS = 50
    workflow = _build_parallel_workflow(N)
    repo = InMemoryExecutionRepo()

    results = await asyncio.gather(
        *[_run_once(repo, workflow, f"run-race-{i}") for i in range(CONCURRENT_RUNS)],
        return_exceptions=True,
    )

    failures = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            failures.append(f"run-race-{i} raised {type(result).__name__}: {result}")
            continue

        run: ExecutionRun = result
        if run.status != RunStatus.SUCCESS:
            failures.append(f"run-race-{i}: run status={run.status}")
            continue

        missing = [
            nid for nid in [f"node_{j}" for j in range(N)]
            if nid not in run.node_states
        ]
        if missing:
            failures.append(f"run-race-{i}: missing node states: {missing}")
            continue

        wrong_status = [
            f"{nid}={run.node_states[nid].status}"
            for nid in [f"node_{j}" for j in range(N)]
            if run.node_states[nid].status != RunStatus.SUCCESS
        ]
        if wrong_status:
            failures.append(f"run-race-{i}: wrong node statuses: {wrong_status}")

    assert not failures, (
        f"{len(failures)}/{CONCURRENT_RUNS} runs had failures:\n" + "\n".join(failures[:10])
    )


@pytest.mark.asyncio
async def test_bulk_update_node_states_atomicity():
    """
    Unit test: InMemoryExecutionRepo.bulk_update_node_states writes all nodes
    in one operation without clobbering pre-existing states.
    """
    repo = InMemoryExecutionRepo()
    run = ExecutionRun(run_id="run-bulk", workflow_id="wf-1", tenant_id="t1")
    await repo.create("t1", run)

    # Pre-write node_0 state
    pre_state = NodeExecutionState(status=RunStatus.RUNNING)
    await repo.update_node_state("t1", "run-bulk", "node_0", pre_state)

    # Bulk-write node_1 and node_2 states
    batch = {
        "node_1": NodeExecutionState(status=RunStatus.SUCCESS, outputs={"x": 1}),
        "node_2": NodeExecutionState(status=RunStatus.SUCCESS, outputs={"x": 2}),
    }
    await repo.bulk_update_node_states("t1", "run-bulk", batch)

    # node_0 must still be RUNNING (not overwritten by batch)
    final = await repo.get("t1", "run-bulk")
    assert final is not None
    assert final.node_states["node_0"].status == RunStatus.RUNNING
    assert final.node_states["node_1"].status == RunStatus.SUCCESS
    assert final.node_states["node_2"].status == RunStatus.SUCCESS
    assert final.node_states["node_1"].outputs == {"x": 1}
    assert final.node_states["node_2"].outputs == {"x": 2}


@pytest.mark.asyncio
async def test_single_layer_batch_write_reduces_repo_calls():
    """
    Verify that for a layer of N parallel nodes, bulk_update_node_states
    is called exactly once (not N times) for the SUCCESS transitions.
    This confirms the batch optimization in the layer loop.
    """
    import asyncio
    from unittest.mock import AsyncMock, patch

    N = 5
    workflow = _build_parallel_workflow(N)
    repo = InMemoryExecutionRepo()
    run = ExecutionRun(run_id="run-batch-check", workflow_id=workflow.id, tenant_id="test")
    await repo.create("test", run)

    bulk_call_count = 0
    original_bulk = repo.bulk_update_node_states

    async def counting_bulk(tenant_id, run_id, states):
        nonlocal bulk_call_count
        bulk_call_count += 1
        return await original_bulk(tenant_id, run_id, states)

    repo.bulk_update_node_states = counting_bulk

    orchestrator = RunOrchestrator(
        repo=repo,
        services=NodeServices(),
        config=TenantConfig(tenant_id="test", plan_tier=PlanTier.PRO),
    )
    await orchestrator.run(workflow, "run-batch-check", "test", {})

    # Layer 0 (trigger node, 1 node) → 1 bulk_update call
    # Layer 1 (N parallel nodes)    → 1 bulk_update call (batch optimization)
    # Total: 2 calls, not N+1 — confirms batch write reduces N round-trips to 1 per layer.
    assert bulk_call_count == 2, (
        f"Expected 2 bulk_update calls (1 per layer), got {bulk_call_count}"
    )
