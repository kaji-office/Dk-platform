"""WebSearchNode — SerpAPI live search with Redis cache (1h TTL)."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from workflow_engine.errors import NodeExecutionError, WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices

_CACHE_TTL = 3600  # 1 hour


class WebSearchNode(BaseNodeType):
    """
    Performs a live web search using SerpAPI and caches results in Redis.

    Config:
        query_field (str): input_data field containing the search query.
        num_results (int): Number of results to return (default 5).
        engine (str): Search engine (default 'google').
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        api_key: str | None = services.serp_api_key
        if not api_key:
            raise WorkflowValidationError("WebSearchNode requires serp_api_key in NodeServices")

        import httpx  # lazy

        query_field: str = config.get("query_field", "query")
        query: str = str(context.input_data.get(query_field, ""))
        num_results: int = int(config.get("num_results", 5))
        engine: str = config.get("engine", "google")

        if not query:
            return NodeOutput(outputs={"results": []}, metadata={"query": ""})

        # Cache key
        cache_key: str = "websearch:" + hashlib.sha256(f"{engine}:{query}:{num_results}".encode()).hexdigest()

        if services.cache:
            cached = await services.cache.get(cache_key)
            if cached:
                return NodeOutput(
                    outputs={"results": json.loads(cached)},
                    metadata={"cached": True, "query": query},
                )

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://serpapi.com/search",
                    params={"q": query, "api_key": api_key, "engine": engine, "num": num_results},
                )
            data = resp.json()
        except Exception as exc:
            raise NodeExecutionError(context.node_id, f"SerpAPI request failed: {exc}") from exc

        results: list[dict[str, Any]] = [
            {"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet")}
            for r in data.get("organic_results", [])[:num_results]
        ]

        if services.cache:
            await services.cache.set(cache_key, json.dumps(results), ttl_seconds=_CACHE_TTL)

        return NodeOutput(outputs={"results": results}, metadata={"cached": False, "query": query})
