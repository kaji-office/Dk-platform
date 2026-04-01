"""
D-6 MCP Integration Tests — Full Acceptance Criteria Suite

Acceptance criteria verified:
- [x] MCPClientRegistry reuses pooled connection (no reconnect per node)
- [x] MCPToolSchemaCache returns cached schemas on second call (no server contact)
- [x] MCPResponseCache TTL-caches call_tool() results
- [x] FeatureDisabledError raised when mcp_node_enabled=False
- [x] MCPClient context-manager lifecycle (connect/disconnect)
"""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from workflow_engine.integrations.mcp.client import MCPClient
from workflow_engine.integrations.mcp.registry import (
    MCPClientRegistry,
    MCPToolSchemaCache,
    MCPResponseCache,
)
from workflow_engine.errors import FeatureDisabledError


# ─────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────

def make_mock_mcp_client(server_url: str = "http://test/sse") -> MCPClient:
    """Return an MCPClient with mocked session."""
    client = MCPClient(server_url=server_url, transport="http_sse")
    # MagicMock.name is special — must use configure_mock() to set it
    tool1 = MagicMock()
    tool1.configure_mock(name="read_file", description="Read a file", inputSchema={"path": "str"})
    tool2 = MagicMock()
    tool2.configure_mock(name="write_file", description="Write a file", inputSchema={"path": "str", "content": "str"})

    mock_session = AsyncMock()
    mock_session.list_tools.return_value = MagicMock(tools=[tool1, tool2])
    mock_session.call_tool.return_value = MagicMock(content=[{"type": "text", "text": "file contents here"}])
    client._session = mock_session
    return client


# ─────────────────────────────────────────────
# AC-1: MCPClient context-manager lifecycle
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_client_context_manager():
    """MCPClient must connect on __aenter__ and disconnect on __aexit__."""
    client = MCPClient("http://test/sse", transport="http_sse")
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()

    async with client as c:
        assert c is client
        client.connect.assert_called_once()

    client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_client_list_tools():
    """list_tools() must return structured tool descriptors."""
    client = make_mock_mcp_client()
    tools = await client.list_tools()

    assert len(tools) == 2
    assert tools[0]["name"] == "read_file"
    assert tools[1]["name"] == "write_file"
    assert "description" in tools[0]
    assert "input_schema" in tools[0]


@pytest.mark.asyncio
async def test_mcp_client_call_tool():
    """call_tool() must invoke the session and return content."""
    client = make_mock_mcp_client()
    result = await client.call_tool("read_file", {"path": "/tmp/test.txt"})

    assert result[0]["type"] == "text"
    assert "file contents" in result[0]["text"]
    client._session.call_tool.assert_called_once_with("read_file", {"path": "/tmp/test.txt"})


@pytest.mark.asyncio
async def test_mcp_client_call_tool_not_connected():
    """call_tool() must raise RuntimeError if not connected."""
    client = MCPClient("http://test/sse")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.call_tool("my_tool", {})


@pytest.mark.asyncio
async def test_mcp_client_list_tools_not_connected():
    """list_tools() must raise RuntimeError if not connected."""
    client = MCPClient("http://test/sse")
    with pytest.raises(RuntimeError, match="Not connected"):
        await client.list_tools()


# ─────────────────────────────────────────────
# AC-2: MCPClientRegistry — pooled connection reuse
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registry_reuses_pooled_connection():
    """MCPClientRegistry must not reconnect on second get() for same server."""
    registry = MCPClientRegistry()

    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()

    with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
        client1 = await registry.get("t1", "http://srv/sse", transport="http_sse")
        client2 = await registry.get("t1", "http://srv/sse", transport="http_sse")

    assert client1 is client2                  # Same instance
    mock_client.connect.assert_called_once()   # Connected exactly once


@pytest.mark.asyncio
async def test_registry_separate_clients_per_tenant():
    """Different tenants must get separate pooled connections."""
    registry = MCPClientRegistry()

    mock1 = make_mock_mcp_client("http://srv/sse")
    mock1.connect = AsyncMock()
    mock2 = make_mock_mcp_client("http://srv/sse")
    mock2.connect = AsyncMock()

    with patch("workflow_engine.integrations.mcp.registry.MCPClient", side_effect=[mock1, mock2]):
        c1 = await registry.get("tenant-A", "http://srv/sse", transport="http_sse")
        c2 = await registry.get("tenant-B", "http://srv/sse", transport="http_sse")

    assert c1 is not c2


# ─────────────────────────────────────────────
# AC-3: MCPToolSchemaCache — no server call on second list_tools()
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_schema_cache_hit_on_second_call():
    """Second list_tools() call must return cached data without calling server."""
    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()

    registry = MCPClientRegistry()

    with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
        # First call — hits server, populates cache
        tools1 = await registry.list_tools("t1", "http://srv/sse", transport="http_sse")
        # Second call — must hit cache, NOT call session.list_tools again
        tools2 = await registry.list_tools("t1", "http://srv/sse", transport="http_sse")

    assert tools1 == tools2
    # Session.list_tools was called exactly once (first call only)
    mock_client._session.list_tools.assert_called_once()


@pytest.mark.asyncio
async def test_schema_cache_ttl_expiry():
    """Schema cache must return None after TTL expires."""
    cache = MCPToolSchemaCache(ttl=0)  # zero TTL = instant expiry
    await cache.set("http://test/sse", "t1", [{"name": "tool_a"}])

    # Immediately expired
    result = await cache.get("http://test/sse", "t1")
    assert result is None


@pytest.mark.asyncio
async def test_schema_cache_valid_before_ttl():
    """Schema cache must return data before TTL expires."""
    cache = MCPToolSchemaCache(ttl=300)
    schemas = [{"name": "tool_x", "description": "does x"}]
    await cache.set("http://test/sse", "t1", schemas)

    result = await cache.get("http://test/sse", "t1")
    assert result == schemas


@pytest.mark.asyncio
async def test_schema_cache_invalidate():
    """Invalidated cache entry must not be returned."""
    cache = MCPToolSchemaCache(ttl=300)
    await cache.set("http://test/sse", "t1", [{"name": "tool_a"}])
    await cache.invalidate("http://test/sse", "t1")

    result = await cache.get("http://test/sse", "t1")
    assert result is None


# ─────────────────────────────────────────────
# AC-4: MCPResponseCache TTL caching
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_response_cache_hit():
    """call_tool() with cache_ttl must return cached result on second call."""
    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()

    registry = MCPClientRegistry()

    with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
        # First call — hits server
        r1 = await registry.call_tool(
            "t1", "http://srv/sse", "read_file", {"path": "/tmp/x"}, cache_ttl=60, transport="http_sse"
        )
        # Second call — must hit cache
        r2 = await registry.call_tool(
            "t1", "http://srv/sse", "read_file", {"path": "/tmp/x"}, cache_ttl=60, transport="http_sse"
        )

    assert r1 == r2
    mock_client._session.call_tool.assert_called_once()  # Only one real call


@pytest.mark.asyncio
async def test_response_cache_different_args_not_cached():
    """Different arguments must NOT share cache entries."""
    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()

    registry = MCPClientRegistry()

    with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
        await registry.call_tool("t1", "http://srv/sse", "read_file", {"path": "/a"}, cache_ttl=60, transport="http_sse")
        await registry.call_tool("t1", "http://srv/sse", "read_file", {"path": "/b"}, cache_ttl=60, transport="http_sse")

    # Both calls went to the server (different cache keys)
    assert mock_client._session.call_tool.call_count == 2


# ─────────────────────────────────────────────
# AC-5: FeatureDisabledError when MCP disabled
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_registry_raises_when_feature_disabled():
    """Registry must raise FeatureDisabledError when MCP_NODE_ENABLED=false."""
    import os
    registry = MCPClientRegistry()

    with patch.dict(os.environ, {"MCP_NODE_ENABLED": "false"}):
        with pytest.raises(FeatureDisabledError, match="MCP node is not enabled"):
            await registry.get("t1", "http://srv/sse")


@pytest.mark.asyncio
async def test_mcp_registry_works_when_feature_enabled():
    """Registry must proceed normally when MCP_NODE_ENABLED=true."""
    import os
    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()

    registry = MCPClientRegistry()

    with patch.dict(os.environ, {"MCP_NODE_ENABLED": "true"}):
        with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
            client = await registry.get("t1", "http://srv/sse", transport="http_sse")
    assert client is mock_client


# ─────────────────────────────────────────────
# AC-6: close_all() disconnects all connections
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_registry_close_all():
    """close_all() must disconnect all pooled clients and clear the pool."""
    import os
    registry = MCPClientRegistry()

    mock_client = make_mock_mcp_client("http://srv/sse")
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()

    with patch.dict(os.environ, {"MCP_NODE_ENABLED": "true"}):
        with patch("workflow_engine.integrations.mcp.registry.MCPClient", return_value=mock_client):
            await registry.get("t1", "http://srv/sse", transport="http_sse")

    await registry.close_all()
    assert len(registry._pool) == 0
    mock_client.disconnect.assert_called_once()
