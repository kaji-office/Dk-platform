"""
D-7 Cache Module Tests — Full Acceptance Criteria Suite

Acceptance criteria verified:
- [x] Cache hit returns WITHOUT calling LLM provider
- [x] Semantic cache similarity threshold configurable per tenant
- [x] Cache eviction does not raise — returns None gracefully
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

from workflow_engine.cache.redis_cache import RedisCache
from workflow_engine.cache.key_builder import CacheKeyBuilder
from workflow_engine.cache.semantic_cache import SemanticCache
from workflow_engine.cache.cached_llm import CachedLLMProvider


# ─────────────────────────────────────────────
# HELPERS / FIXTURES
# ─────────────────────────────────────────────

def make_redis_client(stored: dict = None):
    """Fake async Redis client backed by an in-memory dict."""
    store = dict(stored or {})
    client = AsyncMock()

    async def _get(key): return store.get(key)
    async def _set(key, value): store[key] = value
    async def _setex(key, ttl, value): store[key] = value
    async def _delete(key): store.pop(key, None)
    async def _exists(key): return int(key in store)
    async def _ttl(key): return -1 if key in store else -2

    client.get.side_effect = _get
    client.set.side_effect = _set
    client.setex.side_effect = _setex
    client.delete.side_effect = _delete
    client.exists.side_effect = _exists
    client.ttl.side_effect = _ttl
    return client, store


def make_embed_fn(vector: list[float] | None = None):
    """Return async embed fn that returns a fixed vector."""
    vec = vector or [0.1] * 10

    async def embed(text: str) -> list[float]:
        return vec

    return embed


# ─────────────────────────────────────────────
# Section 1: RedisCache
# ─────────────────────────────────────────────

class TestRedisCache:

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        client, _ = make_redis_client()
        cache = RedisCache(client)
        await cache.set("k1", "hello")
        result = await cache.get("k1")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_set_with_ttl_calls_setex(self):
        client, _ = make_redis_client()
        cache = RedisCache(client)
        await cache.set("k2", "world", ttl_seconds=60)
        client.setex.assert_called_once_with("k2", 60, "world")

    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self):
        client, _ = make_redis_client()
        cache = RedisCache(client)
        result = await cache.get("nonexistent")
        assert result is None

    # AC: Cache eviction does not raise — returns None gracefully
    @pytest.mark.asyncio
    async def test_get_on_redis_error_returns_none_gracefully(self):
        client = AsyncMock()
        client.get.side_effect = ConnectionError("Redis down")
        cache = RedisCache(client)
        result = await cache.get("any_key")
        assert result is None   # No raise — returns None

    @pytest.mark.asyncio
    async def test_set_on_redis_error_does_not_raise(self):
        client = AsyncMock()
        client.setex.side_effect = ConnectionError("Redis down")
        client.set.side_effect = ConnectionError("Redis down")
        cache = RedisCache(client)
        # Must not raise
        await cache.set("k", "v", ttl_seconds=30)

    @pytest.mark.asyncio
    async def test_delete_on_error_does_not_raise(self):
        client = AsyncMock()
        client.delete.side_effect = ConnectionError("Redis down")
        cache = RedisCache(client)
        await cache.delete("k")  # Must not raise

    @pytest.mark.asyncio
    async def test_delete_removes_key(self):
        client, store = make_redis_client({"to_delete": "bye"})
        cache = RedisCache(client)
        await cache.delete("to_delete")
        assert "to_delete" not in store

    @pytest.mark.asyncio
    async def test_key_prefix_applied(self):
        client, store = make_redis_client()
        cache = RedisCache(client, key_prefix="tenant-1")
        await cache.set("my_key", "value")
        assert "tenant-1:my_key" in store

    @pytest.mark.asyncio
    async def test_get_bytes_decoded_to_str(self):
        client = AsyncMock()
        client.get.return_value = b"binary_value"
        cache = RedisCache(client)
        result = await cache.get("k")
        assert result == "binary_value"


# ─────────────────────────────────────────────
# Section 2: CacheKeyBuilder
# ─────────────────────────────────────────────

class TestCacheKeyBuilder:

    def test_build_is_deterministic(self):
        """Same inputs must always produce the same key."""
        kb = CacheKeyBuilder(tenant_id="t1", namespace="llm")
        k1 = kb.build("gpt-4o", "Hello!", {"temperature": 0.5})
        k2 = kb.build("gpt-4o", "Hello!", {"temperature": 0.5})
        assert k1 == k2

    def test_build_different_prompts_produce_different_keys(self):
        kb = CacheKeyBuilder(tenant_id="t1")
        k1 = kb.build("gpt-4o", "Prompt A")
        k2 = kb.build("gpt-4o", "Prompt B")
        assert k1 != k2

    def test_build_different_params_produce_different_keys(self):
        kb = CacheKeyBuilder(tenant_id="t1")
        k1 = kb.build("gpt-4o", "Same prompt", {"temperature": 0.0})
        k2 = kb.build("gpt-4o", "Same prompt", {"temperature": 1.0})
        assert k1 != k2

    def test_build_params_dict_order_independent(self):
        """Params must be hashed deterministically regardless of dict key order."""
        kb = CacheKeyBuilder(tenant_id="t1")
        k1 = kb.build("m1", "p", {"a": 1, "b": 2})
        k2 = kb.build("m1", "p", {"b": 2, "a": 1})
        assert k1 == k2

    def test_build_cross_tenant_isolation(self):
        """Keys for same prompt/model must differ across tenants."""
        kb1 = CacheKeyBuilder(tenant_id="tenant-A")
        kb2 = CacheKeyBuilder(tenant_id="tenant-B")
        assert kb1.build("m", "p") != kb2.build("m", "p")

    def test_build_contains_all_components(self):
        kb = CacheKeyBuilder(tenant_id="t-abc", namespace="cache")
        key = kb.build("gemini-1.5-pro", "hello")
        assert "dk" in key
        assert "cache" in key
        assert "t-abc" in key
        assert "gemini-1.5-pro" in key

    def test_build_semantic_shorter_key(self):
        kb = CacheKeyBuilder(tenant_id="t1")
        key = kb.build_semantic("gpt-4o", "prompt")
        assert "semantic" in key
        assert "t1" in key

    def test_model_with_slashes_sanitised(self):
        kb = CacheKeyBuilder(tenant_id="t1")
        key = kb.build("google/gemini-flash", "p")
        assert "/" not in key


# ─────────────────────────────────────────────
# Section 3: SemanticCache
# ─────────────────────────────────────────────

class TestSemanticCache:

    def _make_pool(self, fetch_row=None, execute_result="DELETE 0"):
        """Mock asyncpg pool that supports async context manager on acquire()."""
        from contextlib import asynccontextmanager

        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=fetch_row)
        conn.execute = AsyncMock(return_value=execute_result)

        @asynccontextmanager
        async def _acquire():
            yield conn

        pool = MagicMock()
        pool.acquire = _acquire
        return pool, conn

    @pytest.mark.asyncio
    async def test_cache_hit_above_threshold(self):
        """get() must return response when similarity >= threshold."""
        pool, conn = self._make_pool(
            fetch_row={"response": "cached answer", "similarity": 0.97}
        )
        sc = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        result = await sc.get("t1", "key1", "What is AI?")
        assert result == "cached answer"

    @pytest.mark.asyncio
    async def test_cache_miss_below_threshold(self):
        """get() must return None when similarity < threshold."""
        pool, conn = self._make_pool(
            fetch_row={"response": "old answer", "similarity": 0.80}
        )
        sc = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        result = await sc.get("t1", "key1", "Something different")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_miss_no_rows(self):
        """get() must return None when no rows in DB."""
        pool, conn = self._make_pool(fetch_row=None)
        sc = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        result = await sc.get("t1", "key1", "any prompt")
        assert result is None

    # AC: Semantic cache similarity threshold configurable per tenant
    @pytest.mark.asyncio
    async def test_threshold_configurable(self):
        """Lower threshold allows a wider similarity window."""
        pool_strict, conn_strict = self._make_pool(
            fetch_row={"response": "answer", "similarity": 0.88}
        )
        pool_loose, conn_loose = self._make_pool(
            fetch_row={"response": "answer", "similarity": 0.88}
        )
        sc_strict = SemanticCache(pool_strict, make_embed_fn(), similarity_threshold=0.95)
        sc_loose  = SemanticCache(pool_loose,  make_embed_fn(), similarity_threshold=0.80)

        result_strict = await sc_strict.get("t1", "k", "p")
        result_loose  = await sc_loose.get("t1", "k", "p")

        assert result_strict is None    # 0.88 < 0.95 → MISS
        assert result_loose == "answer" # 0.88 >= 0.80 → HIT

    # AC: Cache eviction does not raise — returns None gracefully
    @pytest.mark.asyncio
    async def test_get_on_db_error_returns_none(self):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _acquire():
            raise OSError("DB down")
            yield  # pragma: no cover

        pool = MagicMock()
        pool.acquire = _acquire
        sc = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        result = await sc.get("t1", "k", "p")
        assert result is None   # No raise

    @pytest.mark.asyncio
    async def test_set_calls_db_upsert(self):
        pool, conn = self._make_pool()
        sc = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        await sc.set("t1", "k1", "What is AI?", "AI is artificial intelligence.")
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "INSERT INTO semantic_cache" in call_args[0]

    @pytest.mark.asyncio
    async def test_set_on_error_does_not_raise(self):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _acquire():
            raise OSError("DB down")
            yield  # pragma: no cover

        pool = MagicMock()
        pool.acquire = _acquire
        sc = SemanticCache(pool, make_embed_fn())
        await sc.set("t1", "k", "p", "r")  # Must not raise

    @pytest.mark.asyncio
    async def test_purge_expired_returns_count(self):
        pool, conn = self._make_pool(execute_result="DELETE 3")
        sc = SemanticCache(pool, make_embed_fn())
        count = await sc.purge_expired()
        assert count == 3


# ─────────────────────────────────────────────
# Section 4: CachedLLMProvider — core AC
# ─────────────────────────────────────────────

class TestCachedLLMProvider:

    def _make_provider(self):
        provider = AsyncMock()
        provider.complete = AsyncMock(return_value="LLM response")
        provider.embed = AsyncMock(return_value=[0.1] * 10)
        return provider

    def _make_cached_llm(self, provider=None, redis_client=None, with_semantic=False):
        if provider is None:
            provider = self._make_provider()
        if redis_client is None:
            redis_client, _ = make_redis_client()
        redis = RedisCache(redis_client)
        kb = CacheKeyBuilder(tenant_id="t1")
        semantic = None
        if with_semantic:
            pool, conn = AsyncMock(), AsyncMock()
            conn.fetchrow.return_value = None
            conn.execute.return_value = "DELETE 0"
            pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
            pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
            semantic = SemanticCache(pool, make_embed_fn(), similarity_threshold=0.95)
        return CachedLLMProvider(provider, redis, kb, semantic_cache=semantic), provider

    # AC: Cache hit returns WITHOUT calling LLM provider
    @pytest.mark.asyncio
    async def test_redis_hit_does_not_call_provider(self):
        """If Redis has a cached response, provider.complete() must NOT be called."""
        provider = self._make_provider()
        client, store = make_redis_client()
        redis = RedisCache(client)
        kb = CacheKeyBuilder(tenant_id="t1")
        cached_llm = CachedLLMProvider(provider, redis, kb)

        # Pre-populate Redis with the exact cache key
        key = kb.build("default", "Hello?")
        store[key] = "cached response"  # bypass Redis mock to ensure hit

        # Re-wire get to return from store
        async def _get(k): return store.get(k)
        client.get.side_effect = _get

        result = await cached_llm.complete("Hello?")

        assert result == "cached response"
        provider.complete.assert_not_called()   # ← core acceptance criterion

    @pytest.mark.asyncio
    async def test_cache_miss_calls_provider(self):
        """On cache miss, provider.complete() must be called exactly once."""
        cached_llm, provider = self._make_cached_llm()
        result = await cached_llm.complete("New prompt")
        assert result == "LLM response"
        provider.complete.assert_called_once_with("New prompt")

    @pytest.mark.asyncio
    async def test_cache_miss_writes_to_redis(self):
        """On provider call, response must be written to Redis."""
        client, store = make_redis_client()
        provider = self._make_provider()
        redis = RedisCache(client)
        kb = CacheKeyBuilder(tenant_id="t1")
        cached_llm = CachedLLMProvider(provider, redis, kb)

        await cached_llm.complete("Store me")
        # After first call, key should be in Redis store
        assert any("t1" in k and len(v) > 0 for k, v in store.items())

    @pytest.mark.asyncio
    async def test_second_call_hits_redis_not_provider(self):
        """Second identical call must read from Redis without calling provider."""
        cached_llm, provider = self._make_cached_llm()

        r1 = await cached_llm.complete("Same prompt", model="default")
        r2 = await cached_llm.complete("Same prompt", model="default")

        assert r1 == r2
        # Provider called exactly once (first call only)
        assert provider.complete.call_count == 1

    @pytest.mark.asyncio
    async def test_semantic_hit_does_not_call_provider(self):
        """Semantic cache hit must also prevent calling provider.complete()."""
        provider = self._make_provider()
        client, store = make_redis_client()
        redis = RedisCache(client)
        kb = CacheKeyBuilder(tenant_id="t1")

        # Mock semantic cache to return a hit
        sem = AsyncMock()
        sem.get = AsyncMock(return_value="semantic cached response")
        sem.set = AsyncMock()

        cached_llm = CachedLLMProvider(provider, redis, kb, semantic_cache=sem)
        result = await cached_llm.complete("Semantically similar prompt", model="gemini")

        assert result == "semantic cached response"
        provider.complete.assert_not_called()  # ← core acceptance criterion

    # AC: Cache eviction does not raise — returns None gracefully
    @pytest.mark.asyncio
    async def test_redis_error_falls_through_to_provider(self):
        """If Redis throws, provider must still be called (no propagated exception)."""
        provider = self._make_provider()
        client = AsyncMock()
        client.get.side_effect = ConnectionError("Redis down")
        client.setex.side_effect = ConnectionError("Redis down")
        client.set.side_effect = ConnectionError("Redis down")
        redis = RedisCache(client)
        kb = CacheKeyBuilder(tenant_id="t1")
        cached_llm = CachedLLMProvider(provider, redis, kb)

        result = await cached_llm.complete("Fallback prompt")
        assert result == "LLM response"     # Provider still served
        provider.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_delegates_to_provider(self):
        """embed() should pass through to the underlying provider."""
        cached_llm, provider = self._make_cached_llm()
        result = await cached_llm.embed("embed me")
        provider.embed.assert_called_once_with("embed me")
