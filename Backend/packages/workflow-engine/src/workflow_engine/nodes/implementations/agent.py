"""AgentNode — autonomous tool-calling loop (LLM ↔ tools until plain-text response)."""
from __future__ import annotations

from typing import Any

from workflow_engine.errors import NodeExecutionError, WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_MAX_LOOPS = 10


class AgentNode(BaseNodeType):
    """
    Runs an agent loop: calls the LLM, executes tool calls it requests,
    feeds results back, and repeats until the LLM returns plain text.

    Config:
        model, system_prompt, tools (list of tool defs), tool_source, max_loops
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        if services.llm is None:
            raise WorkflowValidationError("AgentNode requires a configured LLMPort")

        model: str = config.get("model", "gemini-2.0-flash")
        system_prompt: str = config.get("system_prompt", "You are a helpful assistant.")
        tool_source: str = config.get("tool_source", "config")
        max_loops: int = int(config.get("max_loops", _MAX_LOOPS))
        tools: list[dict[str, Any]] = list(config.get("tools") or [])

        # Fetch MCP tool schemas if tool_source is "mcp"
        if tool_source == "mcp" and services.mcp_registry is not None:
            try:
                mcp_tools: list[dict[str, Any]] = await services.mcp_registry.list_tools(context.tenant_id)
                tools = tools + mcp_tools
            except Exception as exc:
                raise NodeExecutionError(context.node_id, f"Failed to fetch MCP tools: {exc}") from exc

        prompt = str(context.input_data.get("prompt", ""))
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        all_tool_calls: list[dict[str, Any]] = []

        for _ in range(max_loops):
            extra: dict[str, Any] = {"model": model, "messages": messages}
            if tools:
                extra["tools"] = tools

            response = await services.llm.complete(prompt, **extra)

            # If response is plain text (no tool call), we're done
            if isinstance(response, str):
                return NodeOutput(
                    outputs={"result": response, "tool_calls": all_tool_calls},
                    metadata={"loops": len(all_tool_calls) + 1, "model": model},
                )

            # Response is a tool call dict
            if isinstance(response, dict) and response.get("tool_call"):
                tool_call = response["tool_call"]
                all_tool_calls.append(tool_call)
                # Append tool result as assistant/tool pair
                messages.append({"role": "assistant", "content": None, "tool_call": tool_call})
                messages.append({"role": "tool", "content": str(tool_call.get("result", ""))})
                continue

            # Unexpected response shape — treat as final
            return NodeOutput(
                outputs={"result": str(response), "tool_calls": all_tool_calls},
                metadata={"loops": len(all_tool_calls), "model": model},
            )

        raise NodeExecutionError(context.node_id, f"AgentNode exceeded max_loops={max_loops}")
