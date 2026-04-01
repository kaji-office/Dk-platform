import pytest
from prometheus_client import REGISTRY

from workflow_engine.observability.metrics import (
    record_workflow_run,
    record_node_execution,
    record_llm_usage,
    WORKFLOW_RUN_COUNTER,
    LLM_TOKEN_COUNTER
)

def test_prometheus_workflow_metric():
    before = REGISTRY.get_sample_value('dk_workflow_runs_total', {'tenant_id': 't1', 'status': 'success'}) or 0.0
    record_workflow_run("t1", "success")
    after = REGISTRY.get_sample_value('dk_workflow_runs_total', {'tenant_id': 't1', 'status': 'success'})
    assert after == before + 1.0


def test_prometheus_node_metric():
    # observe doesn't have a direct get_sample_value, we check sum/count
    before_count = REGISTRY.get_sample_value('dk_node_execution_seconds_count', {'tenant_id': 't2', 'node_type': 'agent', 'status': 'completed'}) or 0.0
    record_node_execution("t2", "agent", "completed", 1.5)
    after_count = REGISTRY.get_sample_value('dk_node_execution_seconds_count', {'tenant_id': 't2', 'node_type': 'agent', 'status': 'completed'})
    assert after_count == before_count + 1.0


def test_prometheus_llm_metric():
    before_in = REGISTRY.get_sample_value('dk_llm_tokens_total', {'tenant_id': 't3', 'model': 'gpt-4', 'token_type': 'input'}) or 0.0
    before_out = REGISTRY.get_sample_value('dk_llm_tokens_total', {'tenant_id': 't3', 'model': 'gpt-4', 'token_type': 'output'}) or 0.0
    
    record_llm_usage("t3", "gpt-4", 1500, 350)
    
    after_in = REGISTRY.get_sample_value('dk_llm_tokens_total', {'tenant_id': 't3', 'model': 'gpt-4', 'token_type': 'input'})
    after_out = REGISTRY.get_sample_value('dk_llm_tokens_total', {'tenant_id': 't3', 'model': 'gpt-4', 'token_type': 'output'})
    
    assert after_in == before_in + 1500
    assert after_out == before_out + 350
