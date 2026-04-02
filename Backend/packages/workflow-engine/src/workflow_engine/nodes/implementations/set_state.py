"""SetStateNode — stores key/value pairs in run-scoped Redis state."""
from __future__ import annotations

from typing import Any

from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_STATE_TTL = 86_400  # 24h — matches run TTL


class SetStateNode(BaseNodeType):
    """
    Stores key/value pairs in the run-scoped Redis state store.
    Downstream nodes read from context.state.

    Config:
        mappings (dict[str, str]): {state_key: input_field} pairs to store.
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        mappings: dict[str, str] = dict(config.get("mappings") or {})
        updated_state: dict[str, Any] = {}

        import json
        for state_key, input_field in mappings.items():
            value = context.input_data.get(input_field, context.input_data.get(state_key))
            updated_state[state_key] = value

            if services.cache:
                full_key = f"state:{context.run_id}:{state_key}"
                await services.cache.set(full_key, json.dumps(value), ttl_seconds=_STATE_TTL)
                # Track which keys exist for this run so orchestrator can auto-load context.state
                tracker_key = f"state_keys:{context.run_id}"
                await services.cache.sadd(tracker_key, state_key, ttl_seconds=_STATE_TTL)

        return NodeOutput(outputs={"state": updated_state}, metadata={"keys_set": list(updated_state.keys())})
