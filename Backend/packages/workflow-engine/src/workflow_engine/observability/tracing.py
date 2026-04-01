"""
OpenTelemetry Tracing Integration.
Provides decorators and context managers for detailed distributed tracing spans.
"""
import functools
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# The global tracer for the DK platform SDK
tracer = trace.get_tracer("dk.workflow.engine")

F = TypeVar('F', bound=Callable[..., Any])


def trace_workflow(func: F) -> F:
    """
    Decorator for the orchestrator layer to establish a root trace span 
    for an incoming execution run.
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Tries to determine the workflow and run IDs dynamically from the typical kwargs/args
        run_id = kwargs.get("run_id") or "unknown_run"
        tenant_id = kwargs.get("tenant_id") or "unknown_tenant"
        
        with tracer.start_as_current_span(
            name=f"WorkflowExecution.{func.__name__}",
            attributes={
                "dk.tenant_id": tenant_id,
                "dk.run_id": run_id,
                "dk.system": "workflow_engine"
            }
        ) as span:
            try:
                result = await func(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, description=str(e)))
                raise
                
    return wrapper  # type: ignore


class NodeTracer:
    """
    Context manager to wrap single node executions within a broader trace.
    Usage:
        async with NodeTracer(tenant_id, run_id, node_def) as span:
            # execute node
    """
    
    def __init__(self, tenant_id: str, run_id: str, node_id: str, node_type: str) -> None:
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.node_id = node_id
        self.node_type = node_type
        
    def __enter__(self) -> trace.Span:
        self.span = tracer.start_span(
            name=f"NodeExecution.{self.node_type}",
            attributes={
                "dk.tenant_id": self.tenant_id,
                "dk.run_id": self.run_id,
                "dk.node_id": self.node_id,
                "dk.node_type": self.node_type,
            }
        )
        self._ctx_mgr = trace.use_span(self.span, end_on_exit=False)
        self._ctx_mgr.__enter__()
        return self.span
        
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            self.span.record_exception(exc_val)
            self.span.set_status(Status(StatusCode.ERROR, description=str(exc_val)))
        else:
            self.span.set_status(Status(StatusCode.OK))
            
        self._ctx_mgr.__exit__(exc_type, exc_val, exc_tb)
        self.span.end()
