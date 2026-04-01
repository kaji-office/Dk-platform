import pytest
from pydantic import ValidationError

from workflow_engine.models import (
    EdgeDefinition,
    ExecutionRun,
    NodeDefinition,
    PlanTier,
    RunStatus,
    TenantConfig,
    UserModel,
    UserRole,
    WorkflowDefinition,
)


def test_node_definition_validation():
    # Valid
    node = NodeDefinition(id="node-1", type="LLMNode")
    assert node.id == "node-1"
    assert node.position == {"x": 0.0, "y": 0.0}

    # Invalid
    with pytest.raises(ValidationError):
        NodeDefinition(id="node-1")  # missing type

def test_workflow_definition_validation():
    workflow = WorkflowDefinition(
        id="wf-1",
        nodes={"node-1": NodeDefinition(id="node-1", type="TriggerNode")},
        edges=[EdgeDefinition(id="edge-1", source_node="node-1", target_node="node-2")]
    )
    assert workflow.id == "wf-1"
    assert len(workflow.nodes) == 1
    assert len(workflow.edges) == 1

def test_execution_run_validation():
    run = ExecutionRun(run_id="run-1", workflow_id="wf-1", tenant_id="t-1")
    assert run.status == RunStatus.QUEUED

    with pytest.raises(ValidationError):
        ExecutionRun(run_id="run-1")  # missing workflow and tenant

def test_tenant_config_validation():
    tenant = TenantConfig(tenant_id="t-1")
    assert tenant.plan_tier == PlanTier.FREE

    tenant_pro = TenantConfig(tenant_id="t-2", plan_tier=PlanTier.PRO)
    assert tenant_pro.plan_tier == PlanTier.PRO

def test_user_model_validation():
    user = UserModel(id="u-1", email="test@example.com")
    assert user.role == UserRole.VIEWER
    assert user.mfa_enabled is False
