"""Integration test for the full RunOrchestrator lifecycle."""
import asyncio
from typing import Any

import pytest

from workflow_engine.execution import RunOrchestrator
from workflow_engine.models import (
    EdgeDefinition, ExecutionRun, NodeDefinition, 
    RunStatus, TenantConfig, WorkflowDefinition
)
from workflow_engine.models.tenant import PIIPolicy
from workflow_engine.nodes import NodeServices
from workflow_engine.nodes.registry import NodeType
from workflow_engine.errors import NodeExecutionError

from tests.test_execution.test_engine import MockRepo


@pytest.mark.asyncio
async def test_orchestrator_full_run():
    # Setup mock repo and simple DAG
    # trigger[payload] -> transform[output] -> output[value]
    
    repo = MockRepo()
    services = NodeServices()
    config = TenantConfig(tenant_id="t1", pii_policy=PIIPolicy.SCAN_WARN)
    
    definition = WorkflowDefinition(
        id="wf-1",
        tenant_id="t1",
        name="Test Workflow",
        nodes={
            "n-trigger": NodeDefinition(
                id="n-trigger",
                type=NodeType.MANUAL_TRIGGER,
                config={}
            ),
            "n-transform": NodeDefinition(
                id="n-transform",
                type=NodeType.CODE_EXECUTION,
                config={"code": "output = input['payload']['x'] * 2", "timeout_seconds": 5}
            ),
            "n-output": NodeDefinition(
                id="n-output",
                type=NodeType.OUTPUT,
                config={"value_field": "output"}
            )
        },
        edges=[
            EdgeDefinition(id="e1", source_node="n-trigger", target_node="n-transform", source_port="payload", target_port="payload"),
            EdgeDefinition(id="e2", source_node="n-transform", target_node="n-output", source_port="", target_port="default"),
        ]
    )
    
    # Initialize run in db
    await repo.create("t1", ExecutionRun(run_id="run-1", workflow_id="wf-1", tenant_id="t1", status=RunStatus.QUEUED))
    
    orchestrator = RunOrchestrator(repo, services, config)
    
    run = await orchestrator.run(
        workflow_def=definition,
        run_id="run-1",
        tenant_id="t1",
        trigger_input={"x": 21}
    )
    
    assert run is not None
    if run.status == RunStatus.FAILED:
        for nid, state in run.node_states.items():
            print(f"Node {nid} failed: {state.error}")
    assert run.status == RunStatus.SUCCESS
    
    # The output node maps value_field 'output' -> 'value'
    assert run.output_data == {"value": 42}
    
    # Check node states
    assert run.node_states["n-trigger"].status == RunStatus.SUCCESS
    assert run.node_states["n-transform"].status == RunStatus.SUCCESS
    assert run.node_states["n-output"].status == RunStatus.SUCCESS
    assert run.node_states["n-transform"].outputs == {"output": 42}


@pytest.mark.asyncio
async def test_orchestrator_max_depth():
    repo = MockRepo()
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    with pytest.raises(NodeExecutionError, match="Max runtime depth"):
        await orchestrator.run(
            workflow_def=WorkflowDefinition(id="w1", nodes={}, edges=[]),
            run_id="r1", tenant_id="t1", trigger_input={}, current_depth=6
        )

@pytest.mark.asyncio
async def test_orchestrator_empty_graph():
    repo = MockRepo()
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1"))
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    run = await orchestrator.run(
        workflow_def=WorkflowDefinition(id="w1", nodes={}, edges=[]),
        run_id="r1", tenant_id="t1", trigger_input={}
    )
    assert run.status == RunStatus.SUCCESS

@pytest.mark.asyncio
async def test_orchestrator_cancel_mid_run():
    repo = MockRepo()
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1", status=RunStatus.QUEUED))
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    definition = WorkflowDefinition(
        id="w1", nodes={
            "n1": NodeDefinition(id="n1", type=NodeType.MANUAL_TRIGGER),
            "n2": NodeDefinition(id="n2", type=NodeType.NOTE),
        }, 
        edges=[EdgeDefinition(id="e1", source_node="n1", target_node="n2", source_port="default", target_port="default")]
    )
    
    # We want to cancel it AFTER n1, before n2. We can do this by hooking repo.get
    from unittest.mock import patch
    original_get = repo.get
    async def mock_get(tid, rid):
        run = await original_get(tid, rid)
        if run and "n1" in run.node_states and run.node_states["n1"].status == RunStatus.SUCCESS:
            run.status = RunStatus.CANCELLED
        return run
        
    with patch.object(repo, "get", side_effect=mock_get):
        run = await orchestrator.run(
            workflow_def=definition, run_id="r1", tenant_id="t1", trigger_input={}
        )
    assert run.status == RunStatus.CANCELLED

@pytest.mark.asyncio
async def test_orchestrator_pii_blocked():
    repo = MockRepo()
    config = TenantConfig(tenant_id="t1", pii_policy=PIIPolicy.SCAN_BLOCK)
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1", status=RunStatus.QUEUED))
    
    orchestrator = RunOrchestrator(repo, NodeServices(), config)
    definition = WorkflowDefinition(
        id="w1", nodes={"n1": NodeDefinition(id="n1", type=NodeType.MANUAL_TRIGGER)}, edges=[]
    )
    
    from unittest.mock import patch
    from workflow_engine.errors import PIIBlockedError
    with patch("workflow_engine.execution.orchestrator.PIIScanner.scan_dict", side_effect=PIIBlockedError("PII")):
        run = await orchestrator.run(
            workflow_def=definition, run_id="r1", tenant_id="t1", trigger_input={"text": "Hello 123-456-789!"}
        )
    assert run.status == RunStatus.FAILED
    assert "PII" in run.node_states["n1"].error

@pytest.mark.asyncio
async def test_orchestrator_node_exception():
    repo = MockRepo()
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1"))
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    definition = WorkflowDefinition(
        id="w1", nodes={"n1": NodeDefinition(id="n1", type=NodeType.CODE_EXECUTION, config={"code": "1/0"})}, edges=[]
    )
    
    run = await orchestrator.run(
        workflow_def=definition, run_id="r1", tenant_id="t1", trigger_input={}
    )
    assert run.status == RunStatus.FAILED
    assert "division by zero" in run.node_states["n1"].error

@pytest.mark.asyncio
async def test_orchestrator_cancel_and_resume():
    repo = MockRepo()
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1", status=RunStatus.QUEUED))
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    await orchestrator.cancel("t1", "r1")
    run = await repo.get("t1", "r1")
    assert run.status == RunStatus.CANCELLED
    
    run.status = RunStatus.WAITING_HUMAN
    await repo.update_state("t1", "r1", run)
    
    minimal_wf = WorkflowDefinition(id="w1", nodes={}, edges=[])
    await orchestrator.resume("t1", "r1", "n1", minimal_wf, {"approved": True})
    run = await repo.get("t1", "r1")
    # No descendants from n1 → resume completes workflow as SUCCESS
    assert run.status in (RunStatus.RUNNING, RunStatus.SUCCESS)
    assert run.node_states["n1"].outputs == {"approved": True}

@pytest.mark.asyncio
async def test_orchestrator_resume_invalid():
    repo = MockRepo()
    await repo.create("t1", ExecutionRun(run_id="r1", workflow_id="w1", tenant_id="t1", status=RunStatus.RUNNING))
    orchestrator = RunOrchestrator(repo, NodeServices(), TenantConfig(tenant_id="t1"))
    
    minimal_wf = WorkflowDefinition(id="w1", nodes={}, edges=[])
    with pytest.raises(NodeExecutionError, match="not waiting for human input"):
        await orchestrator.resume("t1", "r1", "n1", minimal_wf, {})

@pytest.mark.asyncio
async def test_get_node_def_missing():
    orchestrator = RunOrchestrator(MockRepo(), NodeServices(), TenantConfig(tenant_id="t1"))
    definition = WorkflowDefinition(id="w1", nodes={}, edges=[])
    with pytest.raises(NodeExecutionError, match="omitted"):
        orchestrator._get_node_def(definition, "n99")
