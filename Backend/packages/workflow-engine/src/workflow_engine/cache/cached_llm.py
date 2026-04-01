"""
CachedLLMProvider — LLM call interceptor with two-tier cache.

Wraps any LLMPort implementation:
  Tier 1 (fast): RedisCache — exact key match (model + prompt + params)
  Tier 2 (smart): SemanticCache — embedding similarity (pgvector)

Flow:
    1. Build deterministic cache key via CacheKeyBuilder
    2. Check Redis (Tier 1) → HIT: return immediately
    3. Check SemanticCache (Tier 2) → HIT: populate Redis + return
    4. Call LLM provider (MISS) → populate both caches + return

AC: "Cache hit returns without calling LLM provider" — verified by:
    - if tier-1 or tier-2 hit, provider.complete() is never invoked.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from workflow_engine.ports import LLMPort
from workflow_engine.cache.redis_cache import RedisCache
from workflow_engine.cache.semantic_cache import SemanticCache
from workflow_engine.cache.key_builder import CacheKeyBuilder

logger = logging.getLogger("dk.cache.llm")


class CachedLLMProvider(LLMPort):
    """
    Two-tier caching wrapper around any LLMPort implementation.

    Args:
        provider:          The underlying LLM provider (Gemini, OpenAI, etc.).
        redis_cache:       Tier-1 exact-match Redis cache.
        semantic_cache:    Tier-2 pgvector similarity cache (optional).
        key_builder:       CacheKeyBuilder scoped to tenant.
        redis_ttl_seconds: TTL for Redis entries (default: 1 hour).
    """

    def __init__(
        self,
        provider: LLMPort,
        redis_cache: RedisCache,
        key_builder: CacheKeyBuilder,
        semantic_cache: SemanticCache | None = None,
        redis_ttl_seconds: int = 3600,
    ) -> None:
        self._provider = provider
        self._redis = redis_cache
        self._semantic = semantic_cache
        self._kb = key_builder
        self._redis_ttl = redis_ttl_seconds

    async def complete(self, prompt: str, **params: Any) -> str:
        """
        Return LLM completion, serving from cache when possible.

        AC: Cache hit returns without calling LLM provider.
        """
        model = params.get("model", "default")
        cache_key = self._kb.build(model=model, prompt=prompt, params=params)

        # ── Tier 1: Redis exact-match ──────────────────────────────────────
        cached = await self._redis.get(cache_key)
        if cached is not None:
            logger.info(f"Cache HIT (Redis tier-1) key={cache_key!r}")
            return cached

        # ── Tier 2: Semantic similarity ────────────────────────────────────
        tenant_id = self._kb.tenant_id
        if self._semantic is not None:
            semantic_key = self._kb.build_semantic(model=model, prompt=prompt)
            sem_cached = await self._semantic.get(
                tenant_id=tenant_id,
                cache_key=semantic_key,
                prompt=prompt,
            )
            if sem_cached is not None:
                logger.info(f"Cache HIT (semantic tier-2) key={semantic_key!r}")
                # Back-fill Redis so next identical call is instant
                await self._redis.set(cache_key, sem_cached, ttl_seconds=self._redis_ttl)
                return sem_cached

        # ── MISS: call provider ────────────────────────────────────────────
        logger.debug(f"Cache MISS — calling LLM provider key={cache_key!r}")
        response = await self._provider.complete(prompt, **params)

        # Write-through to both caches
        await self._redis.set(cache_key, response, ttl_seconds=self._redis_ttl)
        if self._semantic is not None:
            semantic_key = self._kb.build_semantic(model=model, prompt=prompt)
            await self._semantic.set(
                tenant_id=tenant_id,
                cache_key=semantic_key,
                prompt=prompt,
                response=response,
                metadata={"model": model, "params": params},
            )

        return response

    async def embed(self, text: str, **params: Any) -> list[float]:
        """Embeddings are not cached (used for cache lookup themselves)."""
        return await self._provider.embed(text, **params)
