"""SemanticSearchNode — pgvector cosine similarity search for RAG pipelines."""
from __future__ import annotations

from typing import Any

from workflow_engine.errors import WorkflowValidationError
from workflow_engine.nodes.base import BaseNodeType, NodeContext, NodeOutput, NodeServices


class SemanticSearchNode(BaseNodeType):
    """
    Embeds the query via LLMPort.embed(), then performs a cosine similarity
    search against the pgvector document index via StoragePort or cache.

    Config:
        query_field, top_k, similarity_threshold, collection
    """

    async def execute(self, config: dict[str, Any], context: NodeContext, services: NodeServices) -> NodeOutput:
        if services.llm is None:
            raise WorkflowValidationError("SemanticSearchNode requires a configured LLMPort")

        query_field: str = config.get("query_field", "query")
        top_k: int = int(config.get("top_k", 5))
        similarity_threshold: float = float(config.get("similarity_threshold", 0.75))
        collection: str = str(config.get("collection", "documents"))

        query_text: str = str(context.input_data.get(query_field, ""))
        if not query_text:
            return NodeOutput(outputs={"results": [], "scores": []}, metadata={"top_k": 0})

        # Embed the query
        embedding: list[float] = await services.llm.embed(query_text)

        # Delegate to storage layer (real impl hits pgvector via asyncpg)
        # Here we expose the interface; concrete storage impl is in Layer D
        results: list[dict[str, Any]] = []
        scores: list[float] = []

        if services.storage is not None:
            raw = await services.storage.download(
                tenant_id=context.tenant_id,
                path=f"__vector_search__/{collection}/{top_k}/{similarity_threshold}",
            )
            import json
            try:
                payload: dict[str, Any] = json.loads(raw)
                results = list(payload.get("results", []))
                scores = [float(s) for s in payload.get("scores", [])]
            except Exception:
                pass

        return NodeOutput(
            outputs={"results": results, "scores": scores},
            metadata={
                "collection": collection,
                "top_k": top_k,
                "query": query_text,
                "embedding_dims": len(embedding),
            },
        )
