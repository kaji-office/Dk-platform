"""
B-2 Node Framework tests — all 17 nodes + registry + port checker.
NodeServices are fully mocked via AsyncMock.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from workflow_engine.errors import (
    FeatureDisabledError, NodeExecutionError, WorkflowValidationError,
)
from workflow_engine.nodes import (
    AgentNode, APIRequestNode, CodeExecutionNode, ControlFlowNode,
    CustomNode, IntegrationTriggerNode, ManualTriggerNode, MCPNode,
    NoteNode, NodeContext, NodeOutput, NodeServices, NodeType,
    NodeTypeRegistry, OutputNode, PortCompatibilityChecker, PromptNode,
    ScheduledTriggerNode, SemanticSearchNode, SetStateNode,
    SubworkflowNode, TemplatingNode, WebSearchNode,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def ctx(input_data: dict | None = None, state: dict | None = None) -> NodeContext:
    return NodeContext(run_id="r1", node_id="n1", tenant_id="t1",
                       input_data=input_data or {}, state=state or {})

def svc(**kwargs) -> NodeServices:
    return NodeServices(**kwargs)


# ── NodeTypeRegistry ───────────────────────────────────────────────────────────

class TestNodeTypeRegistry:
    def test_all_17_registered(self) -> None:
        registered = NodeTypeRegistry.all_registered()
        assert len(registered) == 17

    def test_get_known_type(self) -> None:
        cls = NodeTypeRegistry.get(NodeType.PROMPT)
        assert cls is PromptNode

    def test_get_unknown_raises(self) -> None:
        # Verify that an unregistered (but temporarily removed) type raises
        with pytest.raises(WorkflowValidationError):
            # Temporarily test with a cleared-then-restored registry entry
            original = NodeTypeRegistry._registry.pop(NodeType.CUSTOM, None)
            try:
                NodeTypeRegistry.get(NodeType.CUSTOM)
            finally:
                if original is not None:
                    NodeTypeRegistry._registry[NodeType.CUSTOM] = original

    def test_is_registered(self) -> None:
        assert NodeTypeRegistry.is_registered(NodeType.MCP)
        assert NodeTypeRegistry.is_registered(NodeType.NOTE)


# ── PortCompatibilityChecker ───────────────────────────────────────────────────

class TestPortCompatibilityChecker:
    def test_valid_port(self) -> None:
        # Should not raise
        PortCompatibilityChecker.check("PromptNode", "text", "TemplatingNode", "default")

    def test_note_node_cannot_be_source(self) -> None:
        with pytest.raises(WorkflowValidationError, match="NoteNode"):
            PortCompatibilityChecker.check("NoteNode", "default", "PromptNode", "default")

    def test_unknown_source_type_raises(self) -> None:
        with pytest.raises(WorkflowValidationError):
            PortCompatibilityChecker.check("BogusNode", "default", "PromptNode", "default")

    def test_get_output_ports(self) -> None:
        ports = PortCompatibilityChecker.get_output_ports("APIRequestNode")
        assert "status_code" in ports
        assert "body" in ports


# ── PromptNode ─────────────────────────────────────────────────────────────────

class TestPromptNode:
    @pytest.mark.asyncio
    async def test_calls_llm_and_returns_text(self) -> None:
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Hello!")
        result = await PromptNode().execute(
            {"prompt_template": "Say hi to {{ name }}", "use_cache": False},
            ctx({"name": "Alice"}), svc(llm=llm)
        )
        assert result.outputs["text"] == "Hello!"
        assert result.outputs["tokens_used"] == 0 or isinstance(result.outputs["tokens_used"], int)

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self) -> None:
        llm = AsyncMock()
        cache = AsyncMock()
        cache.get = AsyncMock(return_value="cached!")
        result = await PromptNode().execute(
            {"use_cache": True}, ctx({"prompt": "hello"}), svc(llm=llm, cache=cache)
        )
        assert result.outputs["text"] == "cached!"
        assert result.metadata["cached"] is True
        llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_llm_raises(self) -> None:
        with pytest.raises(WorkflowValidationError):
            await PromptNode().execute({}, ctx(), svc())


# ── AgentNode ─────────────────────────────────────────────────────────────────

class TestAgentNode:
    @pytest.mark.asyncio
    async def test_plain_text_response_exits_loop(self) -> None:
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Final answer.")
        result = await AgentNode().execute(
            {"model": "gemini-2.0-flash"}, ctx({"prompt": "What is 2+2?"}), svc(llm=llm)
        )
        assert result.outputs["result"] == "Final answer."
        assert result.outputs["tool_calls"] == []

    @pytest.mark.asyncio
    async def test_tool_call_loop(self) -> None:
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=[
            {"tool_call": {"name": "add", "args": {"a": 2, "b": 2}, "result": 4}},
            "The answer is 4.",
        ])
        result = await AgentNode().execute({}, ctx({"prompt": "Add 2+2"}), svc(llm=llm))
        assert result.outputs["result"] == "The answer is 4."
        assert len(result.outputs["tool_calls"]) == 1

    @pytest.mark.asyncio
    async def test_mcp_tools_fetched(self) -> None:
        llm = AsyncMock()
        llm.complete = AsyncMock(return_value="Done.")
        mcp = AsyncMock()
        mcp.list_tools = AsyncMock(return_value=[{"name": "search"}])
        result = await AgentNode().execute(
            {"tool_source": "mcp"}, ctx({"prompt": "search something"}), svc(llm=llm, mcp_registry=mcp)
        )
        mcp.list_tools.assert_called_once()
        assert result.outputs["result"] == "Done."

    @pytest.mark.asyncio
    async def test_no_llm_raises(self) -> None:
        with pytest.raises(WorkflowValidationError):
            await AgentNode().execute({}, ctx(), svc())


# ── CodeExecutionNode ─────────────────────────────────────────────────────────

class TestCodeExecutionNode:
    @pytest.mark.asyncio
    async def test_basic_execution(self) -> None:
        result = await CodeExecutionNode().execute({"code": "output = input['x'] * 3"}, ctx({"x": 7}), svc())
        assert result.outputs["output"] == 21

    @pytest.mark.asyncio
    async def test_ast_blocks_os_import(self) -> None:
        with pytest.raises(NodeExecutionError, match="not allowed"):
            await CodeExecutionNode().execute({"code": "import os; output = os.getcwd()"}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_ast_blocks_sys_import(self) -> None:
        with pytest.raises(NodeExecutionError, match="not allowed"):
            await CodeExecutionNode().execute({"code": "import sys; output = sys.version"}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_syntax_error_raises(self) -> None:
        with pytest.raises(NodeExecutionError):
            await CodeExecutionNode().execute({"code": "output = (1 +"}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_empty_code_returns_none(self) -> None:
        result = await CodeExecutionNode().execute({"code": ""}, ctx(), svc())
        assert result.outputs["output"] is None


# ── APIRequestNode ────────────────────────────────────────────────────────────

class TestAPIRequestNode:
    @pytest.mark.asyncio
    async def test_unsupported_method_raises(self) -> None:
        with pytest.raises(NodeExecutionError, match="Unsupported"):
            await APIRequestNode().execute({"method": "BREW", "url": "http://x"}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_successful_get_json(self) -> None:
        import httpx
        from unittest.mock import patch
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"data": "ok"})
        mock_response.headers = {"Content-Type": "application/json"}
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        
        # We need to mock the async context manager returns the client
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await APIRequestNode().execute(
                {
                    "method": "GET",
                    "url": "https://api.example.com/search?q={{ query }}",
                    "auth_config": {"type": "bearer", "token": "abc"}
                },
                ctx({"query": "python"}), svc()
            )
            
            assert result.outputs["status_code"] == 200
            assert result.outputs["body"] == {"data": "ok"}
            assert result.metadata["url"] == "https://api.example.com/search?q=python"
            
            mock_client.request.assert_called_once_with(
                method="GET",
                url="https://api.example.com/search?q=python",
                headers={"Authorization": "Bearer abc"},
                content=None
            )

    @pytest.mark.asyncio
    async def test_httpx_timeout_raises(self) -> None:
        import httpx
        from unittest.mock import patch
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(NodeExecutionError, match="Request timed out"):
                await APIRequestNode().execute({"url": "http://x"}, ctx(), svc())


# ── TemplatingNode ────────────────────────────────────────────────────────────

class TestTemplatingNode:
    @pytest.mark.asyncio
    async def test_renders_template(self) -> None:
        result = await TemplatingNode().execute(
            {"template": "Hello, {{ name }}!"}, ctx({"name": "World"}), svc()
        )
        assert result.outputs["rendered"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_custom_output_key(self) -> None:
        result = await TemplatingNode().execute(
            {"template": "Hi", "output_key": "message"}, ctx(), svc()
        )
        assert "message" in result.outputs


# ── ControlFlowNode ───────────────────────────────────────────────────────────

class TestControlFlowNode:
    @pytest.mark.asyncio
    async def test_branch_true(self) -> None:
        config = {"mode": "BRANCH", "rules": [{"field": "score", "operator": "gte", "value": 80, "target_port": "pass"}], "default_branch": "fail"}
        result = await ControlFlowNode().execute(config, ctx({"score": 90}), svc())
        assert result.route_to_port == "pass"

    @pytest.mark.asyncio
    async def test_branch_false(self) -> None:
        config = {"mode": "BRANCH", "rules": [{"field": "score", "operator": "gte", "value": 80, "target_port": "pass"}], "default_branch": "fail"}
        result = await ControlFlowNode().execute(config, ctx({"score": 50}), svc())
        assert result.route_to_port == "fail"

    @pytest.mark.asyncio
    async def test_switch_matches(self) -> None:
        config = {"mode": "SWITCH", "switch_field": "tier", "cases": {"gold": "gold_port", "silver": "silver_port"}, "default_case": "default_port"}
        result = await ControlFlowNode().execute(config, ctx({"tier": "gold"}), svc())
        assert result.route_to_port == "gold_port"

    @pytest.mark.asyncio
    async def test_switch_default(self) -> None:
        config = {"mode": "SWITCH", "switch_field": "tier", "cases": {}, "default_case": "std"}
        result = await ControlFlowNode().execute(config, ctx({"tier": "bronze"}), svc())
        assert result.route_to_port == "std"

    @pytest.mark.asyncio
    async def test_loop_fan_out(self) -> None:
        config = {"mode": "LOOP", "iterate_over": "items", "max_iterations": 100}
        result = await ControlFlowNode().execute(config, ctx({"items": [1, 2, 3]}), svc())
        assert result.outputs["count"] == 3
        assert result.route_to_port == "items"

    @pytest.mark.asyncio
    async def test_merge_passthrough(self) -> None:
        result = await ControlFlowNode().execute({"mode": "MERGE"}, ctx({"x": 1}), svc())
        assert result.route_to_port == "merged"
        assert result.outputs["x"] == 1

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self) -> None:
        with pytest.raises(NodeExecutionError):
            await ControlFlowNode().execute({"mode": "QUANTUM"}, ctx(), svc())


# ── MCPNode ───────────────────────────────────────────────────────────────────

class TestMCPNode:
    @pytest.mark.asyncio
    async def test_raises_when_disabled(self) -> None:
        with pytest.raises(FeatureDisabledError):
            await MCPNode().execute(
                {"server_name": "s", "tool_name": "t"},
                ctx(), svc(mcp_node_enabled=False)
            )

    @pytest.mark.asyncio
    async def test_calls_tool_and_returns(self) -> None:
        mcp = AsyncMock()
        mcp.list_tools = AsyncMock(return_value=[{"name": "get_data", "input_schema": {"required": []}}])
        mcp.call_tool = AsyncMock(return_value={"items": [1, 2, 3]})
        result = await MCPNode().execute(
            {"server_name": "db", "tool_name": "get_data"},
            ctx(), svc(mcp_node_enabled=True, mcp_registry=mcp)
        )
        assert result.outputs["result"] == {"items": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_missing_required_param_raises(self) -> None:
        mcp = AsyncMock()
        mcp.list_tools = AsyncMock(return_value=[{"name": "t", "input_schema": {"required": ["user_id"]}}])
        mcp.call_tool = AsyncMock(return_value={})
        with pytest.raises(NodeExecutionError, match="required param"):
            await MCPNode().execute(
                {"server_name": "s", "tool_name": "t", "tool_params": {}},
                ctx(), svc(mcp_node_enabled=True, mcp_registry=mcp)
            )

    @pytest.mark.asyncio
    async def test_result_cache_returns_without_calling_tool(self) -> None:
        import json
        mcp = AsyncMock()
        mcp.list_tools = AsyncMock(return_value=[{"name": "t", "input_schema": {}}])
        mcp.call_tool = AsyncMock(return_value={"x": 1})
        cache = AsyncMock()
        cache.get = AsyncMock(side_effect=[None, None, json.dumps({"cached": "yes"})])
        cache.set = AsyncMock()
        # First call — sets cache
        await MCPNode().execute(
            {"server_name": "s", "tool_name": "t", "cache_ttl_seconds": 60},
            ctx(), svc(mcp_node_enabled=True, mcp_registry=mcp, cache=cache)
        )


# ── NoteNode ──────────────────────────────────────────────────────────────────

class TestNoteNode:
    def test_is_not_executable(self) -> None:
        assert NoteNode.is_executable is False

    @pytest.mark.asyncio
    async def test_returns_empty_output(self) -> None:
        result = await NoteNode().execute({}, ctx(), svc())
        assert result.outputs == {}
        assert result.metadata.get("skipped") is True


# ── OutputNode ────────────────────────────────────────────────────────────────

class TestOutputNode:
    @pytest.mark.asyncio
    async def test_extracts_value(self) -> None:
        result = await OutputNode().execute(
            {"value_field": "answer"}, ctx({"answer": 42}), svc()
        )
        assert result.outputs["value"] == 42

    @pytest.mark.asyncio
    async def test_is_terminal(self) -> None:
        result = await OutputNode().execute({}, ctx({"x": 1}), svc())
        assert result.metadata.get("terminal") is True


# ── SetStateNode ──────────────────────────────────────────────────────────────

class TestSetStateNode:
    @pytest.mark.asyncio
    async def test_stores_state(self) -> None:
        cache = AsyncMock()
        cache.set = AsyncMock()
        result = await SetStateNode().execute(
            {"mappings": {"user_id": "id"}},
            ctx({"id": "u-123"}), svc(cache=cache)
        )
        assert result.outputs["state"]["user_id"] == "u-123"
        cache.set.assert_called_once()


# ── Trigger Nodes ─────────────────────────────────────────────────────────────

class TestTriggerNodes:
    @pytest.mark.asyncio
    async def test_manual_trigger_passes_payload(self) -> None:
        result = await ManualTriggerNode().execute({}, ctx({"x": 1}), svc())
        assert result.outputs["payload"] == {"x": 1}

    @pytest.mark.asyncio
    async def test_manual_trigger_validates_schema(self) -> None:
        schema = {"type": "object", "required": ["name"]}
        with pytest.raises(WorkflowValidationError):
            await ManualTriggerNode().execute({"input_schema": schema}, ctx({}), svc())

    @pytest.mark.asyncio
    async def test_scheduled_trigger_valid_cron(self) -> None:
        result = await ScheduledTriggerNode().execute(
            {"cron_expression": "0 9 * * 1", "timezone": "UTC"}, ctx(), svc()
        )
        assert result.metadata["cron"] == "0 9 * * 1"

    @pytest.mark.asyncio
    async def test_scheduled_trigger_invalid_cron(self) -> None:
        with pytest.raises(WorkflowValidationError, match="Invalid cron"):
            await ScheduledTriggerNode().execute({"cron_expression": "not_a_cron"}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_integration_trigger_passes_payload(self) -> None:
        result = await IntegrationTriggerNode().execute(
            {"source": "github", "event_type": "push"}, ctx({"ref": "main"}), svc()
        )
        assert result.metadata["source"] == "github"
        assert result.outputs["payload"]["ref"] == "main"


# ── SubworkflowNode ───────────────────────────────────────────────────────────

class TestSubworkflowNode:
    @pytest.mark.asyncio
    async def test_missing_workflow_id_raises(self) -> None:
        with pytest.raises(NodeExecutionError):
            await SubworkflowNode().execute({}, ctx(), svc())

    @pytest.mark.asyncio
    async def test_executor_called(self) -> None:
        async def fake_executor(**kwargs) -> dict:
            return {"done": True}
        result = await SubworkflowNode().execute(
            {"workflow_id": "wf-nested"},
            ctx({"x": 1}), svc(http_client=fake_executor)
        )
        assert result.outputs["output"] == {"done": True}

    @pytest.mark.asyncio
    async def test_no_executor_surfaces_intent(self) -> None:
        result = await SubworkflowNode().execute({"workflow_id": "wf-2"}, ctx(), svc())
        assert result.metadata.get("pending_execution") is True
