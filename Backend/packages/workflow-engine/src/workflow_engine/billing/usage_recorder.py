"""
UsageRecorder - Observes engine events and dumps raw billing telemetry to storage.
"""
from __future__ import annotations

import logging
from datetime import datetime

from workflow_engine.events import EventBus, EventType
from workflow_engine.storage.postgres.billing_repo import PostgresBillingRepository

logger = logging.getLogger("dk.billing.recorder")

class UsageRecorder:
    """
    Subscribes to EventBus and records granular billing telemetry.
    Designed to operate asynchronously to avoid blocking the workflow execution loop.
    """

    def __init__(self, repo: PostgresBillingRepository, bus: EventBus) -> None:
        self._repo = repo
        self._bus = bus
        
    def start(self) -> None:
        """Attach listeners to the event bus."""
        self._bus.subscribe(EventType.NODE_COMPLETED, self._on_node_completed)
        self._bus.subscribe(EventType.NODE_FAILED, self._on_node_completed)
        self._bus.subscribe(EventType.LLM_USAGE_REPORTED, self._on_llm_usage)

    async def _on_node_completed(self, payload: dict) -> None:
        """Record node duration regardless of success/failure."""
        try:
            tenant_id = payload.get("tenant_id")
            run_id = payload.get("run_id")
            node_id = payload.get("node_id")
            node_type = payload.get("node_type", "unknown")
            started = payload.get("started_at")
            ended = payload.get("completed_at", datetime.now().timestamp())
            
            if not all((tenant_id, run_id, node_id, started)):
                return
                
            duration = int((ended - started) * 1000)
            
            await self._repo.record_node_execution(
                tenant_id,
                run_id,
                node_id,
                node_type,
                duration
            )
        except Exception as e:
            logger.error(f"Failed recording node usage telemetry: {e}")

    async def _on_llm_usage(self, payload: dict) -> None:
        """Record precise LLM token usage natively from nodes like prompt/agent."""
        try:
            tenant_id = payload.get("tenant_id")
            run_id = payload.get("run_id")
            model = payload.get("model")
            inputs = payload.get("input_tokens", 0)
            outputs = payload.get("output_tokens", 0)
            cost = payload.get("cost_usd", 0.0)
            
            if not all((tenant_id, run_id, model)):
                return
                
            await self._repo.record_llm_tokens(
                tenant_id,
                run_id,
                model,
                inputs,
                outputs,
                cost
            )
        except Exception as e:
            logger.error(f"Failed recording LLM usage telemetry: {e}")
