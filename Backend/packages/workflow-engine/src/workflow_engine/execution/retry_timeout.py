"""Exponential backoff retries and execution timeout wrappers."""
from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, Coroutine

from workflow_engine.errors import NodeExecutionError


class RetryConfig:
    def __init__(self, max_attempts: int = 3, initial_delay_seconds: float = 1.0, 
                 multiplier: float = 2.0, max_delay_seconds: float = 60.0, jitter: bool = True):
        self.max_attempts = max_attempts
        self.initial_delay_seconds = initial_delay_seconds
        self.multiplier = multiplier
        self.max_delay_seconds = max_delay_seconds
        self.jitter = jitter


class RetryHandler:
    @classmethod
    def compute_backoff(cls, attempt: int, config: RetryConfig) -> float:
        delay = min(
            config.initial_delay_seconds * (config.multiplier ** (attempt - 1)),
            config.max_delay_seconds,
        )
        if config.jitter:
            delay *= random.uniform(0.8, 1.2)
        return float(delay)

    @classmethod
    async def execute_with_retry(
        cls, 
        coro_func: Callable[[], Coroutine[Any, Any, Any]], 
        config: RetryConfig, 
    ) -> Any:
        attempt = 1
        while True:
            try:
                return await coro_func()
            except Exception as e:
                # Do not retry on timeout if we enforce strict
                # Wait, retry limits are just attempts.
                if attempt >= config.max_attempts:
                    raise e
                
                delay = cls.compute_backoff(attempt, config)
                await asyncio.sleep(delay)
                attempt += 1


class TimeoutManager:
    @classmethod
    async def wrap(
        cls,
        coro: Coroutine[Any, Any, Any],
        timeout_seconds: float,
        node_id: str,
    ) -> Any:
        """Execute a coroutine wrapped within an asyncio timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise NodeExecutionError(
                node_id, 
                message=f"Node {node_id} exceeded timeout of {timeout_seconds}s"
            ) from exc
