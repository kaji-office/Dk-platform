"""
D-5 Observability Module — Full Acceptance Criteria Test Suite

Acceptance criteria verified:
- [x] Every execution emits a root span with child spans per node
- [x] run_id appears in all log lines for that execution
- [x] Metrics (Prometheus counters/histograms) published without error
- [x] Error paths in trace_workflow correctly emit ERROR status spans
"""
import json
import logging
import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry import trace

# ─────────────────────────────────────────────
# Setup OTel in-memory provider BEFORE importing tracing module
# ─────────────────────────────────────────────
provider = TracerProvider()
exporter = InMemorySpanExporter()
processor = SimpleSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

from workflow_engine.observability.tracing import trace_workflow, NodeTracer
from workflow_engine.observability.logging import (
    configure_structured_logging,
    get_execution_logger,
    get_logger,
)
from workflow_engine.observability.metrics import (
    record_workflow_run,
    record_node_execution,
    record_llm_usage,
)
from prometheus_client import REGISTRY


# ─────────────────────────────────────────────
# AC-1: Root span with child spans per node
# ─────────────────────────────────────────────

@trace_workflow
async def simulate_workflow(tenant_id: str, run_id: str, nodes: list):
    """Simulated orchestrator that creates child node spans."""
    for node in nodes:
        with NodeTracer(tenant_id=tenant_id, run_id=run_id,
                        node_id=node["id"], node_type=node["type"]):
            pass  # Simulate node work


@pytest.mark.asyncio
async def test_root_span_with_child_spans():
    """Every execution must emit a root span with child spans per node."""
    exporter.clear()

    nodes = [
        {"id": "n1", "type": "llm_prompt"},
        {"id": "n2", "type": "api_request"},
        {"id": "n3", "type": "set_state"},
    ]
    await simulate_workflow(tenant_id="t1", run_id="r1", nodes=nodes)

    spans = exporter.get_finished_spans()
    # 1 root + 3 node child spans = 4 total
    assert len(spans) == 4

    span_names = {s.name for s in spans}
    assert "WorkflowExecution.simulate_workflow" in span_names
    assert "NodeExecution.llm_prompt" in span_names
    assert "NodeExecution.api_request" in span_names
    assert "NodeExecution.set_state" in span_names

    # Root span attributes
    root_span = next(s for s in spans if "WorkflowExecution" in s.name)
    assert root_span.attributes["dk.run_id"] == "r1"
    assert root_span.attributes["dk.tenant_id"] == "t1"

    # All spans must be OK
    for s in spans:
        assert s.status.is_ok, f"Span {s.name} not OK: {s.status}"


@pytest.mark.asyncio
async def test_single_workflow_span_attributes():
    """Root span must carry run_id, tenant_id, and system attributes."""
    exporter.clear()

    @trace_workflow
    async def minimal_run(tenant_id: str, run_id: str):
        pass

    await minimal_run(tenant_id="t-abc", run_id="r-xyz")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.attributes["dk.tenant_id"] == "t-abc"
    assert span.attributes["dk.run_id"] == "r-xyz"
    assert span.attributes["dk.system"] == "workflow_engine"


@pytest.mark.asyncio
async def test_error_in_workflow_sets_error_span():
    """When a workflow raises, the root span must be in ERROR state."""
    exporter.clear()

    @trace_workflow
    async def failing_workflow(tenant_id: str, run_id: str):
        raise RuntimeError("Node timeout")

    with pytest.raises(RuntimeError, match="Node timeout"):
        await failing_workflow(tenant_id="t2", run_id="r2")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == trace.StatusCode.ERROR
    assert "Node timeout" in span.status.description


def test_node_tracer_error_span():
    """NodeTracer must record exception and set ERROR status."""
    exporter.clear()

    with pytest.raises(ValueError, match="bad input"):
        with NodeTracer(tenant_id="t3", run_id="r3", node_id="n-err", node_type="code_exec"):
            raise ValueError("bad input")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == trace.StatusCode.ERROR
    assert "bad input" in span.status.description


# ─────────────────────────────────────────────
# AC-2: run_id appears in all log lines for that execution
# ─────────────────────────────────────────────

def test_run_id_in_all_log_lines(capsys):
    """run_id and tenant_id must appear in every log line for an execution."""
    configure_structured_logging(level=logging.DEBUG)
    logger = get_execution_logger("dk.orchestrator", run_id="run-888", tenant_id="t-888")

    logger.info("Starting execution")
    logger.warning("Quota approaching limit")
    logger.info("Execution complete")

    captured = capsys.readouterr()
    json_lines = [line for line in captured.out.splitlines() if line.strip()]

    assert len(json_lines) >= 3, f"Expected at least 3 log lines, got: {json_lines}"

    for line in json_lines:
        data = json.loads(line)
        assert data.get("run_id") == "run-888", (
            f"run_id missing from log line: {line}"
        )
        assert data.get("tenant_id") == "t-888", (
            f"tenant_id missing from log line: {line}"
        )


def test_standard_logger_structured_json(capsys):
    """Standard logger must emit valid JSON with level, name, message."""
    configure_structured_logging(level=logging.INFO)
    logger = get_logger("dk.test.module")

    logger.info("Hello from test")

    captured = capsys.readouterr()
    lines = [l for l in captured.out.splitlines() if l.strip()]

    assert len(lines) >= 1
    data = json.loads(lines[-1])
    assert data["message"] == "Hello from test"
    assert data["level"] == "INFO"
    assert data["name"] == "dk.test.module"


# ─────────────────────────────────────────────
# AC-3: Prometheus metrics published without error
# ─────────────────────────────────────────────

def test_workflow_run_counter_increments():
    """Prometheus workflow run counter must increment correctly."""
    before = REGISTRY.get_sample_value(
        'dk_workflow_runs_total', {'tenant_id': 't10', 'status': 'success'}
    ) or 0.0
    record_workflow_run("t10", "success")
    after = REGISTRY.get_sample_value(
        'dk_workflow_runs_total', {'tenant_id': 't10', 'status': 'success'}
    )
    assert after == before + 1.0


def test_node_execution_histogram():
    """Node execution histogram must record count and duration."""
    before_count = REGISTRY.get_sample_value(
        'dk_node_execution_seconds_count',
        {'tenant_id': 't11', 'node_type': 'llm_prompt', 'status': 'completed'}
    ) or 0.0
    before_sum = REGISTRY.get_sample_value(
        'dk_node_execution_seconds_sum',
        {'tenant_id': 't11', 'node_type': 'llm_prompt', 'status': 'completed'}
    ) or 0.0

    record_node_execution("t11", "llm_prompt", "completed", 2.5)

    after_count = REGISTRY.get_sample_value(
        'dk_node_execution_seconds_count',
        {'tenant_id': 't11', 'node_type': 'llm_prompt', 'status': 'completed'}
    )
    after_sum = REGISTRY.get_sample_value(
        'dk_node_execution_seconds_sum',
        {'tenant_id': 't11', 'node_type': 'llm_prompt', 'status': 'completed'}
    )

    assert after_count == before_count + 1.0
    assert after_sum == pytest.approx(before_sum + 2.5, abs=0.01)


def test_llm_token_counter_input_output():
    """LLM token counter must separately track input and output tokens."""
    before_in = REGISTRY.get_sample_value(
        'dk_llm_tokens_total', {'tenant_id': 't12', 'model': 'gemini-1.5-pro', 'token_type': 'input'}
    ) or 0.0
    before_out = REGISTRY.get_sample_value(
        'dk_llm_tokens_total', {'tenant_id': 't12', 'model': 'gemini-1.5-pro', 'token_type': 'output'}
    ) or 0.0

    record_llm_usage("t12", "gemini-1.5-pro", 2048, 512)

    after_in = REGISTRY.get_sample_value(
        'dk_llm_tokens_total', {'tenant_id': 't12', 'model': 'gemini-1.5-pro', 'token_type': 'input'}
    )
    after_out = REGISTRY.get_sample_value(
        'dk_llm_tokens_total', {'tenant_id': 't12', 'model': 'gemini-1.5-pro', 'token_type': 'output'}
    )

    assert after_in == before_in + 2048
    assert after_out == before_out + 512


def test_failed_workflow_counter():
    """Workflow failure status must be tracked distinctly from success."""
    before = REGISTRY.get_sample_value(
        'dk_workflow_runs_total', {'tenant_id': 't13', 'status': 'failed'}
    ) or 0.0
    record_workflow_run("t13", "failed")
    after = REGISTRY.get_sample_value(
        'dk_workflow_runs_total', {'tenant_id': 't13', 'status': 'failed'}
    )
    assert after == before + 1.0
