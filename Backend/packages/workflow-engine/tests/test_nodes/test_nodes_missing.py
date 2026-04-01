"""Additional tests to reach 100% coverage on node implementations."""
from __future__ import annotations

import httpx
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from workflow_engine.errors import NodeExecutionError, WorkflowValidationError
from workflow_engine.nodes import (
    APIRequestNode, SemanticSearchNode, WebSearchNode, NodeContext, NodeServices
)

def ctx(input_data: dict | None = None) -> NodeContext:
    return NodeContext(run_id="r1", node_id="n1", tenant_id="t1", input_data=input_data or {})

def svc(**kwargs) -> NodeServices:
    return NodeServices(**kwargs)

class TestAPIRequestNodeDetails:

    @pytest.mark.asyncio
    async def test_auth_basic_and_body(self):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(side_effect=ValueError("Not JSON"))
        mock_response.text = "Plain Text!"
        mock_response.headers = {}
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await APIRequestNode().execute(
                {
                    "method": "POST",
                    "url": "http://x",
                    "body_template": '{"msg": "{{ txt }}"}',
                    "auth_config": {"type": "basic", "username": "usr", "password": "pwd"}
                },
                ctx({"txt": "hello"}), svc()
            )
            
            assert result.outputs["body"] == "Plain Text!"
            
            # Check basic auth is encoded base64(usr:pwd) = b\'dXNyOnB3ZA==\'
            import base64
            enc = base64.b64encode(b"usr:pwd").decode()
            mock_client.request.assert_called_once_with(
                method="POST", url="http://x",
                headers={"Authorization": f"Basic {enc}"},
                content=b'{"msg": "hello"}'
            )

    @pytest.mark.asyncio
    async def test_auth_oauth2(self):
        mock_response = AsyncMock()
        mock_response.json = lambda: {}
        mock_response.headers = {}
        
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            await APIRequestNode().execute(
                {
                    "method": "GET",
                    "url": "http://x",
                    "auth_config": {"type": "oauth2", "access_token": "token123"}
                },
                ctx({}), svc()
            )
            mock_client.request.assert_called_once_with(
                method="GET", url="http://x",
                headers={"Authorization": "Bearer token123"},
                content=None
            )

    @pytest.mark.asyncio
    async def test_request_error(self):
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.RequestError("Host unreachable", request=AsyncMock()))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(NodeExecutionError, match="Request failed"):
                await APIRequestNode().execute({"url": "http://x"}, ctx(), svc())


class TestSemanticSearchNode:
    @pytest.mark.asyncio
    async def test_no_llm_raises(self):
        with pytest.raises(WorkflowValidationError, match="requires a configured LLMPort"):
            await SemanticSearchNode().execute({}, ctx(), svc(llm=None))

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        llm = AsyncMock()
        res = await SemanticSearchNode().execute({"query_field": "q"}, ctx({"q": ""}), svc(llm=llm))
        assert res.outputs["results"] == []
        assert res.metadata["top_k"] == 0

    @pytest.mark.asyncio
    async def test_embed_and_search(self):
        llm = AsyncMock()
        llm.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        
        storage = AsyncMock()
        storage.download = AsyncMock(return_value=json.dumps({
            "results": [{"text": "doc1"}],
            "scores": [0.99]
        }))
        
        res = await SemanticSearchNode().execute(
            {"query_field": "q", "top_k": 1, "similarity_threshold": 0.8, "collection": "docs"},
            ctx({"q": "test query"}), svc(llm=llm, storage=storage)
        )
        
        assert res.outputs["scores"] == [0.99]
        assert res.outputs["results"] == [{"text": "doc1"}]
        assert res.metadata["embedding_dims"] == 3
        storage.download.assert_called_with(tenant_id="t1", path="__vector_search__/docs/1/0.8")

    @pytest.mark.asyncio
    async def test_storage_malformed_json_fallback(self):
        llm = AsyncMock()
        llm.embed = AsyncMock(return_value=[0.1])
        storage = AsyncMock()
        storage.download = AsyncMock(return_value="NOT JSON")
        
        res = await SemanticSearchNode().execute({"query_field": "q"}, ctx({"q": "ping"}), svc(llm=llm, storage=storage))
        assert res.outputs["results"] == []


class TestWebSearchNode:
    @pytest.mark.asyncio
    async def test_disabled(self):
        with pytest.raises(WorkflowValidationError, match="requires serp_api_key"):
             await WebSearchNode().execute({}, ctx(), svc(serp_api_key=None))

    @pytest.mark.asyncio
    async def test_empty_query(self):
        res = await WebSearchNode().execute({"query_field": "query"}, ctx({}), svc(serp_api_key="123"))
        assert res.outputs["results"] == []
        assert res.metadata["query"] == ""

    @pytest.mark.asyncio
    async def test_search_results(self):
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={
            "organic_results": [{"title": "Python", "link": "https://py", "snippet": "A lang"}]
        })
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            res = await WebSearchNode().execute(
                {"query_field": "query", "num_results": 2},
                ctx({"query": "python search"}), svc(serp_api_key="key123")
            )
            assert res.outputs["results"][0]["title"] == "Python"
            assert res.outputs["results"][0]["link"] == "https://py"
            assert res.metadata["cached"] is False
            
            mock_client.get.assert_called_once_with(
                "https://serpapi.com/search",
                params={"q": "python search", "api_key": "key123", "engine": "google", "num": 2}
            )

    @pytest.mark.asyncio
    async def test_search_cache_hit(self):
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=json.dumps([{"title": "Cached", "link": "x", "snippet": "y"}]))
        
        res = await WebSearchNode().execute(
            {"query_field": "q"}, ctx({"q": "test"}), svc(serp_api_key="k", cache=cache)
        )
        assert res.outputs["results"][0]["title"] == "Cached"
        assert res.metadata["cached"] is True
        
    @pytest.mark.asyncio
    async def test_search_error(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Host down", request=AsyncMock()))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(NodeExecutionError, match="SerpAPI request failed"):
                await WebSearchNode().execute({"query_field": "q"}, ctx({"q": "test"}), svc(serp_api_key="k"))
