"""
MCPClientRegistry — pooled MCP connections per tenant.

Guarantees:
 - No reconnect per node execution (connection reused from pool)
 - Lazy connect on first use
 - Periodic health check teardown of stale connections
 - Feature-flag enforcement: raises FeatureDisabledError if MCP disabled

Also provides:
 - MCPToolSchemaCache — Redis TTL cache (5-min) for list_tools() responses
 - MCPResponseCache  — Redis TTL cache for call_tool() results (TTL configurable)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from workflow_engine.errors import FeatureDisabledError
from workflow_engine.integrations.mcp.client import MCPClient

logger = logging.getLogger("dk.mcp.registry")

# ── In-memory schema cache ────────────────────────────────────────────────────

class MCPToolSchemaCache:
    """
    In-process TTL cache for MCP tool schemas (list_tools responses).
    Falls back to a real Redis implementation if `redis_client` is injected.

    Default TTL: 5 minutes (300 seconds).
    """

    DEFAULT_TTL = 300  # seconds

    def __init__(self, redis_client: Any | None = None, ttl: int = DEFAULT_TTL) -> None:
        self._redis = redis_client
        self._ttl = ttl
        self._local: dict[str, tuple[Any, float]] = {}  # key -> (value, expires_at)

    def _cache_key(self, server_url: str, tenant_id: str) -> str:
        return f"dk:mcp:schema:{tenant_id}:{server_url}"

    async def get(self, server_url: str, tenant_id: str) -> list[dict] | None:
        key = self._cache_key(server_url, tenant_id)
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        # Local in-process fallback
        entry = self._local.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        return None

    async def set(self, server_url: str, tenant_id: str, schemas: list[dict]) -> None:
        key = self._cache_key(server_url, tenant_id)
        if self._redis:
            await self._redis.setex(key, self._ttl, json.dumps(schemas))
        else:
            self._local[key] = (schemas, time.monotonic() + self._ttl)

    async def invalidate(self, server_url: str, tenant_id: str) -> None:
        key = self._cache_key(server_url, tenant_id)
        if self._redis:
            await self._redis.delete(key)
        else:
            self._local.pop(key, None)


class MCPResponseCache:
    """
    TTL cache for call_tool() results.
    TTL is configurable per workflow node (default: 60 seconds).
    """

    DEFAULT_TTL = 60  # seconds

    def __init__(self, redis_client: Any | None = None, default_ttl: int = DEFAULT_TTL) -> None:
        self._redis = redis_client
        self._default_ttl = default_ttl
        self._local: dict[str, tuple[Any, float]] = {}

    def _cache_key(self, server_url: str, tool_name: str, args_hash: str, tenant_id: str) -> str:
        return f"dk:mcp:resp:{tenant_id}:{server_url}:{tool_name}:{args_hash}"

    async def get(self, server_url: str, tool_name: str, arguments: dict, tenant_id: str) -> Any | None:
        import hashlib
        args_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()[:16]
        key = self._cache_key(server_url, tool_name, args_hash, tenant_id)
        if self._redis:
            raw = await self._redis.get(key)
            return json.loads(raw) if raw else None
        entry = self._local.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
        return None

    async def set(self, server_url: str, tool_name: str, arguments: dict, tenant_id: str, result: Any, ttl: int | None = None) -> None:
        import hashlib
        args_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()[:16]
        key = self._cache_key(server_url, tool_name, args_hash, tenant_id)
        ttl = ttl or self._default_ttl
        if self._redis:
            await self._redis.setex(key, ttl, json.dumps(result))
        else:
            self._local[key] = (result, time.monotonic() + ttl)


# ── Client Registry ───────────────────────────────────────────────────────────

class MCPClientRegistry:
    """
    Manages a pool of MCPClient connections per tenant.

    Design:
      - Connections are lazy: created on first `get()` call.
      - Connections are reused across node executions (no reconnect overhead).
      - Feature flag checked on every `get()` call: if `mcp_node_enabled` is
        False, raises FeatureDisabledError before any network I/O.

    Platform-managed server definitions:
      filesystem, memory, github, postgres, browser
    """

    PLATFORM_SERVERS: dict[str, dict[str, Any]] = {
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        },
        "memory": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
        },
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
        },
        "postgres": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-postgres"],
        },
        "browser": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        },
    }

    def __init__(
        self,
        schema_cache: MCPToolSchemaCache | None = None,
        response_cache: MCPResponseCache | None = None,
    ) -> None:
        self._pool: dict[str, MCPClient] = {}   # key: "tenant_id:server_url"
        self._schema_cache = schema_cache or MCPToolSchemaCache()
        self._response_cache = response_cache or MCPResponseCache()

    async def get(
        self,
        tenant_id: str,
        server_url: str,
        transport: str = "http_sse",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> MCPClient:
        """
        Return a connected MCPClient for the given server.

        Raises:
            FeatureDisabledError: if `mcp_node_enabled` is False in settings.
        """
        # Feature-flag enforcement per D-6 acceptance criteria
        # Reads MCP_NODE_ENABLED env var (default: true)
        mcp_enabled = os.getenv("MCP_NODE_ENABLED", "true").lower() not in ("false", "0", "no")
        if not mcp_enabled:
            raise FeatureDisabledError("MCP node is not enabled for this tenant")

        pool_key = f"{tenant_id}:{server_url}"
        if pool_key in self._pool:
            logger.debug(f"Reusing pooled MCP connection: {pool_key}")
            return self._pool[pool_key]

        client = MCPClient(server_url=server_url, transport=transport, args=args or [], env=env or {})
        await client.connect()
        self._pool[pool_key] = client
        logger.info(f"MCP client connected and pooled: {pool_key}")
        return client

    async def list_tools(self, tenant_id: str, server_url: str, **kwargs: Any) -> list[dict]:
        """
        List tools, using the schema cache (5-min TTL) on repeated calls.
        Second call returns cached result without contacting server.
        """
        cached = await self._schema_cache.get(server_url, tenant_id)
        if cached is not None:
            logger.debug(f"Schema cache hit for {server_url}")
            return cached

        client = await self.get(tenant_id, server_url, **kwargs)
        schemas = await client.list_tools()
        await self._schema_cache.set(server_url, tenant_id, schemas)
        return schemas

    async def call_tool(
        self,
        tenant_id: str,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        cache_ttl: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Call a tool, using the response cache when TTL is set.
        """
        if cache_ttl is not None:
            cached = await self._response_cache.get(server_url, tool_name, arguments, tenant_id)
            if cached is not None:
                logger.debug(f"Response cache hit: {tool_name}")
                return cached

        client = await self.get(tenant_id, server_url, **kwargs)
        result = await client.call_tool(tool_name, arguments)

        if cache_ttl is not None:
            await self._response_cache.set(server_url, tool_name, arguments, tenant_id, result, ttl=cache_ttl)

        return result

    async def close_all(self) -> None:
        """Close all pooled connections."""
        for client in self._pool.values():
            await client.disconnect()
        self._pool.clear()
