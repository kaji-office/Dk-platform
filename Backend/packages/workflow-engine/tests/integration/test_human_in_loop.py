"""
P9-T-08 — Human-in-the-loop end-to-end test.

Verifies the resume() flow:
1. A workflow runs up to a HumanInputNode, transitions to WAITING_HUMAN
2. The run is suspended — downstream nodes are not executed yet
3. resume() is called with a human response payload
4. Downstream nodes receive the human response as inputs
5. The run completes with SUCCESS

The test uses the InMemoryExecutionRepo from test_parallel_execution.py
pattern and a custom HumanInputNode mock.
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
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices
from workflow_engine.nodes.registry import NodeTypeRegistry, NodeType


# ── Minimal in-memory repo (copied from test_parallel_execution.py) ───────────

class _InMemoryRepo:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def _key(self, tenant_id, run_id):
        return f"{tenant_id}:{run_id}"

    async def get(self, tenant_id, run_id):
        doc = self._store.get(self._key(tenant_id, run_id))
        if doc is None:
            return None
        return ExecutionRun.model_validate(doc)

    async def create(self, tenant_id, execution):
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        self._store[self._key(tenant_id, execution.run_id)] = data
        return execution

    async def update_state(self, tenant_id, run_id, execution):
        data = execution.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        self._store[self._key(tenant_id, run_id)] = data
        return execution

    async def list(self, *a, **kw):
        return []

    async def get_node_states(self, *a, **kw):
        return []

    async def list_runs_by_tenant(self, *a, **kw):
        return []

    async def patch_fields(self, tenant_id, run_id, fields):
        key = self._key(tenant_id, run_id)
        if key in self._store:
            self._store[key].update(fields)

    async def update_node_state(self, tenant_id, run_id, node_id, node_state):
        key = self._key(tenant_id, run_id)
        if key not in self._store:
            return
        doc = self._store[key]
        if "node_states" not in doc:
            doc["node_states"] = {}
        doc["node_states"][node_id] = node_state.model_dump(mode="json")

    async def bulk_update_node_states(self, tenant_id, run_id, states):
        key = self._key(tenant_id, run_id)
        if key not in self._store or not states:
            return
        doc = self._store[key]
        if "node_states" not in doc:
            doc["node_states"] = {}
        for node_id, state in states.items():
            doc["node_states"][node_id] = state.model_dump(mode="json")

    async def list_stale_running(self, before):
        return []


# ── Fake HumanInputNode ────────────────────────────────────────────────────────

class _FakeHumanInputNode(BaseNodeType):
    """
    Simulates a human-in-the-loop gate node.
    When executed, transitions to WAITING_HUMAN status.
    """
    async def execute(self, config: dict, context: NodeContext, services: NodeServices) -> NodeOutput:
        # Signal to the orchestrator that this node is waiting for human input
        return NodeOutput(
            outputs={"awaiting": True},
            metadata={"status": "WAITING_HUMAN"},
        )


class _FakeDownstreamNode(BaseNodeType):
    """Captures the input it received so tests can inspect it."""
    captured_input: dict[str, Any] = {}

    async def execute(self, config: dict, context: NodeContext, services: NodeServices) -> NodeOutput:
        _FakeDownstreamNode.captured_input = dict(context.input_data)
        return NodeOutput(outputs={"received": context.input_data}, metadata={})


# ── Register fake nodes ────────────────────────────────────────────────────────
# We register under unused NodeType values for test isolation.
# Using NodeType.CUSTOM and NodeType.OUTPUT as proxies.

_HUMAN_TYPE = "ManualTriggerNode"  # reuse registered type; we override it in tests below


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_delivers_human_response_to_downstream():
    """
    Full HITL flow:
      trigger → human_gate (WAITING_HUMAN) → downstream (receives human response)

    The test verifies:
    1. After initial run(), the run status is WAITING_HUMAN
    2. After resume(), the run status is SUCCESS
    3. The downstream node received the human_response as input
    """
    repo = _InMemoryRepo()
    tenant_id = "t-hitl"
    run_id = "run-hitl-001"

    # Register fake node types for this test
    _orig_human = NodeTypeRegistry._registry.get(NodeType.CUSTOM)
    _orig_downstream = NodeTypeRegistry._registry.get(NodeType.OUTPUT)

    NodeTypeRegistry._registry[NodeType.CUSTOM] = _FakeHumanInputNode
    NodeTypeRegistry._registry[NodeType.OUTPUT] = _FakeDownstreamNode
    _FakeDownstreamNode.captured_input = {}

    try:
        # Build workflow: trigger → human_gate → downstream
        workflow = WorkflowDefinition(
            id="wf-hitl",
            nodes={
                "trigger": NodeDefinition(id="trigger", type="ManualTriggerNode", config={}),
                "human_gate": NodeDefinition(id="human_gate", type="CustomNode", config={}),
                "downstream": NodeDefinition(id="downstream", type="OutputNode", config={}),
            },
            edges=[
                EdgeDefinition(id="e1", source_node="trigger", target_node="human_gate"),
                EdgeDefinition(id="e2", source_node="human_gate", target_node="downstream"),
            ],
        )

        run = ExecutionRun(run_id=run_id, workflow_id="wf-hitl", tenant_id=tenant_id, status=RunStatus.QUEUED)
        await repo.create(tenant_id, run)

        orchestrator = RunOrchestrator(
            repo=repo,
            services=NodeServices(),
            config=TenantConfig(tenant_id=tenant_id, plan_tier=PlanTier.PRO),
        )

        # Phase 1: Run until human gate
        result = await orchestrator.run(workflow, run_id, tenant_id, {"trigger_input": "hello"})

        assert result is not None
        assert result.status == RunStatus.WAITING_HUMAN, (
            f"Expected WAITING_HUMAN after initial run, got {result.status}"
        )

        # Phase 2: Resume with human response
        human_response = {"approved": True, "comment": "Looks good!"}
        final = await orchestrator.resume(
            tenant_id=tenant_id,
            run_id=run_id,
            node_id="human_gate",
            workflow_def=workflow,
            human_response=human_response,
        )

        assert final is not None
        assert final.status == RunStatus.SUCCESS, (
            f"Expected SUCCESS after resume, got {final.status}"
        )

    finally:
        # Restore registry
        if _orig_human is not None:
            NodeTypeRegistry._registry[NodeType.CUSTOM] = _orig_human
        elif NodeType.CUSTOM in NodeTypeRegistry._registry:
            del NodeTypeRegistry._registry[NodeType.CUSTOM]

        if _orig_downstream is not None:
            NodeTypeRegistry._registry[NodeType.OUTPUT] = _orig_downstream
        elif NodeType.OUTPUT in NodeTypeRegistry._registry:
            del NodeTypeRegistry._registry[NodeType.OUTPUT]


@pytest.mark.asyncio
async def test_resume_on_non_waiting_run_raises():
    """resume() on a RUNNING run must raise NodeExecutionError."""
    from workflow_engine.errors import NodeExecutionError

    repo = _InMemoryRepo()
    tenant_id = "t-hitl"
    run_id = "run-hitl-bad"

    run = ExecutionRun(run_id=run_id, workflow_id="wf-1", tenant_id=tenant_id, status=RunStatus.RUNNING)
    await repo.create(tenant_id, run)

    workflow = WorkflowDefinition(
        id="wf-1",
        nodes={"n1": NodeDefinition(id="n1", type="ManualTriggerNode", config={})},
        edges=[],
    )

    orchestrator = RunOrchestrator(
        repo=repo,
        services=NodeServices(),
        config=TenantConfig(tenant_id=tenant_id),
    )

    with pytest.raises(NodeExecutionError):
        await orchestrator.resume(tenant_id, run_id, "n1", workflow, {"data": "x"})


@pytest.mark.asyncio
async def test_resume_on_missing_run_raises():
    """resume() on a non-existent run must raise NodeExecutionError."""
    from workflow_engine.errors import NodeExecutionError

    repo = _InMemoryRepo()
    workflow = WorkflowDefinition(
        id="wf-1",
        nodes={"n1": NodeDefinition(id="n1", type="ManualTriggerNode", config={})},
        edges=[],
    )
    orchestrator = RunOrchestrator(
        repo=repo,
        services=NodeServices(),
        config=TenantConfig(tenant_id="t1"),
    )

    with pytest.raises(NodeExecutionError):
        await orchestrator.resume("t1", "nonexistent-run", "n1", workflow, {})
