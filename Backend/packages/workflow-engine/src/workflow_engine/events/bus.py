"""
EventBus - async pub/sub for decoupling engine telemetry from core execution.
"""
from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Coroutine

logger = logging.getLogger("dk.events.bus")

class EventType(str, Enum):
    """System-wide event topics."""
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"
    LLM_USAGE_REPORTED = "llm.usage"


# EventHandler signature: async def handler(payload: dict[str, Any]) -> None
EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]

class EventBus:
    """
    Very lightweight async in-memory PubSub bus.
    In the target architecture, this can be swapped with Redis PubSub or Kafka.
    """
    
    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {
            t: [] for t in EventType
        }

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an async handler constraint for an event topic."""
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: EventType, payload: dict[str, Any]) -> None:
        """
        Fire and forget an event. Handlers run as asyncio background tasks.
        """
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            # We schedule background tasks for the handlers to avoid blocking the caller
            # Typically create_task holds weakref, must store if needed long living, 
            # but for telemetry fire-and-forget it's acceptable.
            task = asyncio.create_task(self._safe_invoke(handler, event_type, payload))
            # Just let it run.

    async def _safe_invoke(
        self, handler: EventHandler, event_type: EventType, payload: dict[str, Any]
    ) -> None:
        try:
            await handler(payload)
        except Exception as e:
            logger.error(f"Event handler {handler.__name__} failed on {event_type.value}: {e}")
