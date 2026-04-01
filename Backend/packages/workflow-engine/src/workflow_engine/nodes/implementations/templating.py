"""TemplatingNode — pure Jinja2 data transformation with no code execution."""
from __future__ import annotations

from typing import Any

from jinja2 import Template, TemplateError

from workflow_engine.errors import NodeExecutionError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


class TemplatingNode(BaseNodeType):
    """
    Renders a Jinja2 template against input_data. No code execution.

    Config:
        template (str): Jinja2 template string.
        output_key (str): Key name in outputs dict (default 'rendered').
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        template_str: str = str(config.get("template", ""))
        output_key: str = str(config.get("output_key", "rendered"))

        try:
            rendered = Template(template_str).render(**context.input_data)
        except TemplateError as exc:
            raise NodeExecutionError(context.node_id, f"Template render error: {exc}") from exc

        return NodeOutput(outputs={output_key: rendered})
