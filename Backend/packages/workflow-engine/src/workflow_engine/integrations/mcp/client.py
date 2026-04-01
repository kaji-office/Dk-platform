"""
MCPClient — async wrapper around the MCP SDK.

Supports:
  - http_sse transport (remote servers over HTTP/SSE)
  - stdio transport (local MCP servers spawned as subprocesses)

Design:
  - Lazy connection: `connect()` must be awaited before use.
  - `list_tools()` returns a list of tool descriptors.
  - `call_tool()` invokes a specific tool and returns its result.
  - Context-manager protocol for safe cleanup.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("dk.mcp.client")


class MCPClient:
    """
    Async MCP client wrapping the official mcp SDK.

    Usage (HTTP/SSE):
        async with MCPClient("http://localhost:3000/sse", transport="http_sse") as client:
            tools = await client.list_tools()
            result = await client.call_tool("my_tool", {"arg": "value"})

    Usage (stdio):
        async with MCPClient("npx", transport="stdio", args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]) as client:
            ...
    """

    def __init__(
        self,
        server_url: str,
        transport: str = "http_sse",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.server_url = server_url
        self.transport = transport
        self.args = args or []
        self.env = env or {}
        self._session: Any | None = None
        self._client_ctx: Any | None = None
        self._session_ctx: Any | None = None

    async def connect(self) -> None:
        """Establish the MCP connection."""
        if self.transport == "http_sse":
            await self._connect_sse()
        elif self.transport == "stdio":
            await self._connect_stdio()
        else:
            raise ValueError(f"Unknown transport: {self.transport!r}. Use 'http_sse' or 'stdio'.")

    async def _connect_sse(self) -> None:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        self._client_ctx = sse_client(self.server_url)
        read, write = await self._client_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()
        logger.info(f"MCP connected via SSE to {self.server_url}")

    async def _connect_stdio(self) -> None:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters

        params = StdioServerParameters(
            command=self.server_url,
            args=self.args,
            env=self.env if self.env else None,
        )
        self._client_ctx = stdio_client(params)
        read, write = await self._client_ctx.__aenter__()
        self._session_ctx = ClientSession(read, write)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()
        logger.info(f"MCP connected via stdio to {self.server_url!r}")

    async def disconnect(self) -> None:
        """Cleanly tear down the MCP session."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
        self._session = None
        logger.info("MCP session closed")

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the server's available tools as a list of dicts."""
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")
        response = await self._session.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema,
            }
            for t in response.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """
        Invoke a named tool on the MCP server.

        Returns:
            The raw result content from the server.
        """
        if not self._session:
            raise RuntimeError("Not connected. Call connect() first.")
        result = await self._session.call_tool(tool_name, arguments)
        return result.content

    # ── Context manager ───────────────────────────────────────────────────

    async def __aenter__(self) -> MCPClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()

    def __repr__(self) -> str:
        return f"<MCPClient transport={self.transport!r} url={self.server_url!r} connected={self._session is not None}>"
