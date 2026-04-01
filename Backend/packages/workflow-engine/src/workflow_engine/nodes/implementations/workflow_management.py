"""NoteNode, OutputNode, CustomNode — simple workflow management nodes."""
from __future__ import annotations

from typing import Any

from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


class NoteNode(BaseNodeType):
    """No-op visual documentation node. Skipped entirely by the execution engine."""
    is_executable: bool = False

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        return NodeOutput(outputs={}, metadata={"skipped": True})


class OutputNode(BaseNodeType):
    """
    Terminal node — defines the final API response value for the workflow run.

    Config:
        value_field (str): Input field to expose as the workflow output (default 'output').
        output_key (str): Key name in the final response (default 'value').
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        value_field: str = config.get("value_field", "output")
        output_key: str = config.get("output_key", "value")
        value = context.input_data.get(value_field, context.input_data)
        return NodeOutput(outputs={output_key: value}, metadata={"terminal": True})


class CustomNode(BaseNodeType):
    """
    SDK-team-defined logic primitive that appears as a visual node.
    Routes execution to a registered custom handler via config['handler_key'].
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        # Custom handler resolution is done by the execution engine via registry
        # Here we pass through input data unchanged as a safe default
        return NodeOutput(
            outputs={"output": context.input_data},
            metadata={"handler_key": config.get("handler_key", "")},
        )
