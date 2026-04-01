"""
D-5 Distributed Tracing Tests — isolated provider per test.

These tests verify workflow/node span instrumentation via the
tracing decorators and context managers in observability/tracing.py.
"""
import pytest
from unittest.mock import patch
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry import trace

from workflow_engine.observability.tracing import trace_workflow, NodeTracer


def make_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create an isolated TracerProvider + InMemoryExporter pair."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


@pytest.mark.asyncio
async def test_tracing_workflow_decorator():
    """trace_workflow decorator must emit one span with correct attributes."""
    provider, exporter = make_provider()
    isolated_tracer = provider.get_tracer("dk.workflow")

    @trace_workflow
    async def dummy_wf(tenant_id: str, run_id: str):
        pass

    with patch("workflow_engine.observability.tracing.tracer", isolated_tracer):
        await dummy_wf(tenant_id="t1", run_id="r1")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert "dummy_wf" in span.name or "WorkflowExecution" in span.name
    assert span.attributes.get("dk.tenant_id") == "t1"
    assert span.attributes.get("dk.run_id") == "r1"
    assert span.status.is_ok


def test_tracing_node_context():
    """NodeTracer context manager must emit one completed span."""
    provider, exporter = make_provider()
    isolated_tracer = provider.get_tracer("dk.node")

    with patch("workflow_engine.observability.tracing.tracer", isolated_tracer):
        with NodeTracer(tenant_id="t2", run_id="r2", node_id="n1", node_type="llm") as span:
            assert span.is_recording()

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "NodeExecution.llm"
    assert span.attributes["dk.node_id"] == "n1"
    assert span.attributes["dk.node_type"] == "llm"
    assert span.status.is_ok


def test_tracing_node_exception():
    """NodeTracer must set ERROR status when an exception is raised."""
    provider, exporter = make_provider()
    isolated_tracer = provider.get_tracer("dk.node")

    with patch("workflow_engine.observability.tracing.tracer", isolated_tracer):
        with pytest.raises(ValueError):
            with NodeTracer(tenant_id="t3", run_id="r3", node_id="n2", node_type="script"):
                raise ValueError("Node crash")

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.is_ok is False
    assert span.status.status_code == trace.StatusCode.ERROR
    assert "Node crash" in span.status.description
