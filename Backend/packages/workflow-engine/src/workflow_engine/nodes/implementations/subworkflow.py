"""SubworkflowNode — nests another workflow as a single synchronous node."""
from __future__ import annotations

from typing import Any

from workflow_engine.errors import NodeExecutionError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


class SubworkflowNode(BaseNodeType):
    """
    Executes a referenced workflow inline and returns its output.
    The actual execution is delegated to the ExecutionEngine (Layer C).
    The Layer B interface accepts a callable injected via NodeServices.http_client
    (re-used as a generic executor slot) or via metadata.

    Config:
        workflow_id (str): ID of the nested workflow to execute.
        input_mapping (dict): Maps parent input fields to nested workflow input.
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        workflow_id: str = str(config.get("workflow_id", ""))
        if not workflow_id:
            raise NodeExecutionError(context.node_id, "SubworkflowNode requires workflow_id in config")

        input_mapping: dict[str, str] = dict(config.get("input_mapping") or {})
        nested_input: dict[str, Any] = {
            target: context.input_data.get(source, context.input_data.get(target))
            for target, source in input_mapping.items()
        } or context.input_data

        # The execution engine injects a subworkflow runner via http_client slot
        # at Layer C. For standalone testing, we surface the intent via metadata.
        executor: Any = services.http_client  # injected by ExecutionEngine as a callable
        if executor is not None and callable(executor):
            try:
                result: Any = await executor(
                    workflow_id=workflow_id,
                    input_data=nested_input,
                    tenant_id=context.tenant_id,
                )
            except Exception as exc:
                raise NodeExecutionError(
                    context.node_id, f"Subworkflow '{workflow_id}' failed: {exc}"
                ) from exc
            return NodeOutput(outputs={"output": result}, metadata={"workflow_id": workflow_id})

        # No executor injected — surface intent only (useful in tests)
        return NodeOutput(
            outputs={"output": nested_input},
            metadata={"workflow_id": workflow_id, "pending_execution": True},
        )
