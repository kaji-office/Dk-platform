"""
RedisCache — implements CachePort using aioredis.

Features:
- Full TTL support on every set() call
- Graceful eviction: get() returns None on miss or error (never raises)
- Optional key prefix for namespace isolation per tenant
"""
from __future__ import annotations

import logging
from typing import Any

from workflow_engine.ports import CachePort

logger = logging.getLogger("dk.cache.redis")


class RedisCache(CachePort):
    """
    Redis-backed cache implementing CachePort.

    Args:
        client: An aioredis / redis.asyncio client instance.
        key_prefix: Optional string prefix applied to every key (e.g. tenant_id).

    Example:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://localhost:6379")
        cache = RedisCache(client=r, key_prefix="tenant-abc")
    """

    def __init__(self, client: Any, key_prefix: str = "") -> None:
        self._client = client
        self._prefix = key_prefix

    def _key(self, key: str) -> str:
        """Prepend namespace prefix if set."""
        return f"{self._prefix}:{key}" if self._prefix else key

    # ── CachePort interface ────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        """
        Retrieve a value by key.

        Returns:
            The cached string value, or None on miss, expiry, or error.
        """
        try:
            value = await self._client.get(self._key(key))
            if value is None:
                return None
            return value.decode("utf-8") if isinstance(value, bytes) else value
        except Exception as exc:
            # AC: Cache eviction/miss must never raise — return None gracefully
            logger.warning(f"RedisCache.get() error for key={key!r}: {exc}")
            return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """
        Store a key-value pair with optional TTL.

        Args:
            key: Cache key.
            value: String value to store.
            ttl_seconds: Time-to-live in seconds. None = no expiry.
        """
        try:
            if ttl_seconds is not None:
                await self._client.setex(self._key(key), ttl_seconds, value)
            else:
                await self._client.set(self._key(key), value)
        except Exception as exc:
            logger.warning(f"RedisCache.set() error for key={key!r}: {exc}")

    async def delete(self, key: str) -> None:
        """
        Remove a key from the cache.
        Non-existent keys are ignored (no raise).
        """
        try:
            await self._client.delete(self._key(key))
        except Exception as exc:
            logger.warning(f"RedisCache.delete() error for key={key!r}: {exc}")

    # ── Extras ────────────────────────────────────────────────────────────

    async def exists(self, key: str) -> bool:
        """Return True if the key exists in Redis."""
        try:
            result = await self._client.exists(self._key(key))
            return bool(result)
        except Exception:
            return False

    async def ttl(self, key: str) -> int:
        """Return remaining TTL in seconds (-1 = no expiry, -2 = not found)."""
        try:
            return await self._client.ttl(self._key(key))
        except Exception:
            return -2

    async def sadd(self, key: str, *members: str, ttl_seconds: int | None = None) -> None:
        """Add members to a Redis set, with optional TTL on the set key."""
        try:
            await self._client.sadd(self._key(key), *members)
            if ttl_seconds is not None:
                await self._client.expire(self._key(key), ttl_seconds)
        except Exception as exc:
            logger.warning(f"RedisCache.sadd() error for key={key!r}: {exc}")

    async def smembers(self, key: str) -> set[str]:
        """Return all members of a Redis set as strings."""
        try:
            raw = await self._client.smembers(self._key(key))
            return {m.decode("utf-8") if isinstance(m, bytes) else m for m in raw}
        except Exception as exc:
            logger.warning(f"RedisCache.smembers() error for key={key!r}: {exc}")
            return set()
