"""
Prometheus metrics telemetry for DK Platform.
"""
from typing import Dict
from prometheus_client import Counter, Histogram

# Metrics definition

WORKFLOW_RUN_COUNTER = Counter(
    "dk_workflow_runs_total",
    "Total number of workflow execution attempts",
    ["tenant_id", "status"]
)

NODE_EXEC_TIME_HISTOGRAM = Histogram(
    "dk_node_execution_seconds",
    "Time taken to execute an individual node",
    ["tenant_id", "node_type", "status"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0]
)

LLM_TOKEN_COUNTER = Counter(
    "dk_llm_tokens_total",
    "Tokens sent to/from LLM endpoints",
    labelnames=["tenant_id", "model", "token_type"]  # token_type: "input" or "output"
)

def record_workflow_run(tenant_id: str, status: str) -> None:
    """Increment the global run counter."""
    WORKFLOW_RUN_COUNTER.labels(tenant_id=tenant_id, status=status).inc()

def record_node_execution(tenant_id: str, node_type: str, status: str, duration_sec: float) -> None:
    """Record execution time for a node logic operation."""
    NODE_EXEC_TIME_HISTOGRAM.labels(
        tenant_id=tenant_id, 
        node_type=node_type, 
        status=status
    ).observe(duration_sec)

def record_llm_usage(tenant_id: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Atomically commit tokens to Prometheus gauge vectors."""
    LLM_TOKEN_COUNTER.labels(tenant_id=tenant_id, model=model, token_type="input").inc(input_tokens)
    LLM_TOKEN_COUNTER.labels(tenant_id=tenant_id, model=model, token_type="output").inc(output_tokens)
