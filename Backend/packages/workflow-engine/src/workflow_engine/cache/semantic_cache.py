"""
SemanticCache — embedding-based similarity cache backed by pgvector.

Architecture:
────────────────────────────────────────────────
  on set():
    1. Generate embedding for the prompt (via injected LLM embedder)
    2. Insert (key, prompt, embedding, response, metadata) into `semantic_cache` table

  on get():
    1. Generate embedding for the incoming prompt
    2. Query pgvector for nearest neighbour (cosine distance)
    3. If distance ≤ (1 - similarity_threshold) → cache HIT, return stored response
    4. Otherwise → cache MISS, return None

The similarity_threshold is configurable per tenant (stored in TenantConfig.semantic_cache_similarity_threshold).
Default threshold: 0.95 (configurable, respects engine config).

Schema (managed by migrations, not created here):
    CREATE TABLE semantic_cache (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   TEXT NOT NULL,
        cache_key   TEXT NOT NULL,
        prompt      TEXT NOT NULL,
        response    TEXT NOT NULL,
        embedding   vector(1536),    -- dimension matches embedding model
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        expires_at  TIMESTAMPTZ
    );
    CREATE INDEX ON semantic_cache USING ivfflat (embedding vector_cosine_ops);
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger("dk.cache.semantic")

# Type alias for an async embedding function: (text) -> List[float]
EmbedFn = Callable[[str], Awaitable[list[float]]]


class SemanticCache:
    """
    pgvector-backed semantic similarity cache for LLM responses.

    Args:
        db_pool:            An asyncpg connection pool.
        embed_fn:           Async callable that converts text → embedding vector.
        similarity_threshold: Minimum cosine similarity for a cache hit (0.0–1.0).
                              Default 0.95. Configurable per tenant.
        ttl_seconds:        Optional TTL for entries (None = no expiry).
    """

    TABLE = "semantic_cache"

    def __init__(
        self,
        db_pool: Any,
        embed_fn: EmbedFn,
        similarity_threshold: float = 0.95,
        ttl_seconds: int | None = None,
    ) -> None:
        self._pool = db_pool
        self._embed_fn = embed_fn
        self.similarity_threshold = similarity_threshold
        self._ttl_seconds = ttl_seconds

    # ── Public API ────────────────────────────────────────────────────────

    async def get(
        self,
        tenant_id: str,
        cache_key: str,
        prompt: str,
    ) -> str | None:
        """
        Look up a semantically similar cached response.

        AC: Returns None on miss or error — never raises.
        AC: Similarity threshold is checked against 1 - cosine_distance.

        Returns:
            Cached response string, or None on miss.
        """
        try:
            embedding = await self._embed_fn(prompt)
            embedding_str = self._to_pgvector(embedding)

            query = f"""
                SELECT response,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM {self.TABLE}
                WHERE tenant_id = $2
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY embedding <=> $1::vector
                LIMIT 1
            """
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, embedding_str, tenant_id)

            if row is None:
                logger.debug(f"Semantic cache MISS (no rows) key={cache_key!r}")
                return None

            similarity: float = float(row["similarity"])
            if similarity >= self.similarity_threshold:
                logger.info(
                    f"Semantic cache HIT key={cache_key!r} similarity={similarity:.4f}"
                )
                return row["response"]

            logger.debug(
                f"Semantic cache MISS key={cache_key!r} "
                f"similarity={similarity:.4f} < threshold={self.similarity_threshold}"
            )
            return None

        except Exception as exc:
            # AC: Eviction / errors must never raise — return None gracefully
            logger.warning(f"SemanticCache.get() error: {exc}")
            return None

    async def set(
        self,
        tenant_id: str,
        cache_key: str,
        prompt: str,
        response: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Store a prompt–response pair with its embedding.

        Args:
            tenant_id:  Tenant scoping.
            cache_key:  Built by CacheKeyBuilder.
            prompt:     The original prompt text.
            response:   The LLM response to cache.
            metadata:   Optional JSON metadata (model, params, etc.).
        """
        try:
            embedding = await self._embed_fn(prompt)
            embedding_str = self._to_pgvector(embedding)
            expires_at = None
            if self._ttl_seconds is not None:
                from datetime import timedelta
                expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl_seconds)

            upsert_query = f"""
                INSERT INTO {self.TABLE}
                    (tenant_id, cache_key, prompt, response, embedding, expires_at)
                VALUES ($1, $2, $3, $4, $5::vector, $6)
                ON CONFLICT (tenant_id, cache_key)
                DO UPDATE SET
                    response   = EXCLUDED.response,
                    embedding  = EXCLUDED.embedding,
                    expires_at = EXCLUDED.expires_at
            """
            async with self._pool.acquire() as conn:
                await conn.execute(
                    upsert_query,
                    tenant_id,
                    cache_key,
                    prompt,
                    response,
                    embedding_str,
                    expires_at,
                )
            logger.debug(f"Semantic cache SET key={cache_key!r} tenant={tenant_id}")

        except Exception as exc:
            logger.warning(f"SemanticCache.set() error: {exc}")

    async def delete(self, tenant_id: str, cache_key: str) -> None:
        """Remove a specific cache entry."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    f"DELETE FROM {self.TABLE} WHERE tenant_id = $1 AND cache_key = $2",
                    tenant_id,
                    cache_key,
                )
        except Exception as exc:
            logger.warning(f"SemanticCache.delete() error: {exc}")

    async def purge_expired(self) -> int:
        """Remove all expired entries. Returns count of deleted rows."""
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    f"DELETE FROM {self.TABLE} WHERE expires_at IS NOT NULL AND expires_at <= NOW()"
                )
                # asyncpg returns "DELETE N"
                count = int(result.split()[-1]) if result else 0
                logger.info(f"SemanticCache purged {count} expired entries")
                return count
        except Exception as exc:
            logger.warning(f"SemanticCache.purge_expired() error: {exc}")
            return 0

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_pgvector(embedding: list[float]) -> str:
        """Convert a Python float list to pgvector literal format '[1.0,2.0,...]'."""
        return "[" + ",".join(str(v) for v in embedding) + "]"
