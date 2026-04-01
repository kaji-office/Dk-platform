"""Trigger nodes — ManualTriggerNode, ScheduledTriggerNode, IntegrationTriggerNode."""
from __future__ import annotations

from typing import Any

from croniter import croniter  # type: ignore[import-untyped]
from jsonschema import ValidationError, validate

from workflow_engine.errors import WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


class ManualTriggerNode(BaseNodeType):
    """
    Entry point for UI Run button or POST /v1/workflows/{id}/trigger.
    Validates the incoming payload against an optional input_schema.
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        schema: dict[str, Any] | None = config.get("input_schema")
        if schema:
            try:
                validate(instance=context.input_data, schema=schema)
            except ValidationError as exc:
                raise WorkflowValidationError(f"Trigger payload invalid: {exc.message}") from exc
        return NodeOutput(outputs={"payload": context.input_data}, route_to_port="default")


class ScheduledTriggerNode(BaseNodeType):
    """
    Entry point for cron-scheduled workflow executions.
    Validates cron expression and surfaces schedule metadata.

    Config:
        cron_expression (str): Standard cron (e.g. '0 9 * * 1').
        timezone (str): IANA timezone string (default 'UTC').
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        cron_expr: str = str(config.get("cron_expression", "* * * * *"))
        timezone: str = str(config.get("timezone", "UTC"))

        if not croniter.is_valid(cron_expr):
            raise WorkflowValidationError(f"Invalid cron expression: '{cron_expr}'")

        return NodeOutput(
            outputs={"payload": context.input_data},
            metadata={"cron": cron_expr, "timezone": timezone},
            route_to_port="default",
        )


class IntegrationTriggerNode(BaseNodeType):
    """
    Entry point driven by a third-party event webhook.
    Supported sources: Slack, GitHub, Google Sheets, Salesforce, generic.

    Config:
        source (str): Integration source identifier.
        event_type (str): Specific event to match (e.g. 'push', 'message').
        secret (str): Optional HMAC secret for signature validation.
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        source: str = str(config.get("source", "generic"))
        event_type: str = str(config.get("event_type", "*"))

        # Signature validation would be done at the API layer before reaching the node.
        # Here we pass through the webhook payload.
        return NodeOutput(
            outputs={"payload": context.input_data},
            metadata={"source": source, "event_type": event_type},
            route_to_port="default",
        )
