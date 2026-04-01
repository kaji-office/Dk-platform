"""MCPNode — feature-flagged MCP tool invocation via MCPClientRegistry."""
from __future__ import annotations

import json
from typing import Any

from workflow_engine.errors import FeatureDisabledError, NodeExecutionError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_SCHEMA_CACHE_TTL = 300   # 5 minutes
_RESULT_CACHE_PREFIX = "mcp:result:"
_SCHEMA_CACHE_PREFIX = "mcp:schema:"


class MCPNode(BaseNodeType):
    """
    Feature-flagged direct MCP tool invocation.

    Config:
        server_name (str): MCP server identifier.
        tool_name (str): Tool to call on the server.
        tool_params (dict): Parameters to pass to the tool.
        cache_ttl_seconds (int): Result cache TTL (0 = no cache).
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        # Feature flag enforcement
        if not services.mcp_node_enabled:
            raise FeatureDisabledError("MCP node is not enabled for this tenant")

        if services.mcp_registry is None:
            raise NodeExecutionError(context.node_id, "MCPNode requires mcp_registry in NodeServices")

        server_name: str = str(config.get("server_name", ""))
        tool_name: str = str(config.get("tool_name", ""))
        tool_params: dict[str, Any] = dict(config.get("tool_params") or {})
        cache_ttl: int = int(config.get("cache_ttl_seconds", 0))

        # Tool schema discovery — cached in Redis (TTL 5 min)
        schema_key = f"{_SCHEMA_CACHE_PREFIX}{server_name}:{tool_name}"
        tool_schema: dict[str, Any] | None = None

        if services.cache:
            raw_schema = await services.cache.get(schema_key)
            if raw_schema:
                tool_schema = json.loads(raw_schema)

        if tool_schema is None:
            try:
                schemas: list[dict[str, Any]] = await services.mcp_registry.list_tools(
                    context.tenant_id, server_name=server_name
                )
                tool_schema = next((s for s in schemas if s.get("name") == tool_name), None)
                if tool_schema and services.cache:
                    await services.cache.set(schema_key, json.dumps(tool_schema), ttl_seconds=_SCHEMA_CACHE_TTL)
            except Exception as exc:
                raise NodeExecutionError(context.node_id, f"MCP tool discovery failed: {exc}") from exc

        # Validate tool params against input_schema
        if tool_schema:
            input_schema: dict[str, Any] = tool_schema.get("input_schema") or {}
            required: list[str] = input_schema.get("required") or []
            for req_field in required:
                if req_field not in tool_params:
                    raise NodeExecutionError(
                        context.node_id,
                        f"MCPNode: required param '{req_field}' missing for tool '{tool_name}'",
                    )

        # Result cache check
        if cache_ttl > 0 and services.cache:
            import hashlib
            result_key = _RESULT_CACHE_PREFIX + hashlib.sha256(
                json.dumps({"server": server_name, "tool": tool_name, "params": tool_params}, sort_keys=True).encode()
            ).hexdigest()
            cached_result = await services.cache.get(result_key)
            if cached_result:
                return NodeOutput(
                    outputs={"result": json.loads(cached_result)},
                    metadata={"cached": True, "tool": tool_name},
                )

        # Call the MCP tool
        try:
            result: Any = await services.mcp_registry.call_tool(
                context.tenant_id, server_name=server_name, tool_name=tool_name, params=tool_params
            )
        except Exception as exc:
            raise NodeExecutionError(context.node_id, f"MCP tool call failed: {exc}") from exc

        # Cache the result
        if cache_ttl > 0 and services.cache:
            import hashlib
            result_key = _RESULT_CACHE_PREFIX + hashlib.sha256(
                json.dumps({"server": server_name, "tool": tool_name, "params": tool_params}, sort_keys=True).encode()
            ).hexdigest()
            await services.cache.set(result_key, json.dumps(result), ttl_seconds=cache_ttl)

        return NodeOutput(
            outputs={"result": result},
            metadata={"cached": False, "tool": tool_name, "server": server_name},
        )
