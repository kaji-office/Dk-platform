"""Scheduler service orchestration."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from workflow_engine.models import ScheduleModel
from workflow_engine.ports import ScheduleRepository
from workflow_engine.scheduler.cron_utils import CronUtils

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages trigger lifecycle, registration, and scheduling ticks."""

    def __init__(self, repo: ScheduleRepository):
        self.repo = repo

    async def register(self, tenant_id: str, schedule: ScheduleModel, from_time: datetime | None = None) -> ScheduleModel:
        """Stores & computes next_fire_at for a schedule."""
        schedule.next_fire_at = CronUtils.compute_next_fire(
            schedule.cron_expression, schedule.timezone, from_time=from_time
        )
        schedule.is_active = True
        return await self.repo.create(tenant_id, schedule)

    async def deactivate(self, tenant_id: str, schedule_id: str) -> ScheduleModel | None:
        """Stops future fires for a selected schedule."""
        schedule = await self.repo.get(tenant_id, schedule_id)
        if not schedule:
            return None

        schedule.is_active = False
        schedule.next_fire_at = None
        return await self.repo.update(tenant_id, schedule_id, schedule)

    async def tick(self, current_time: datetime | None = None) -> list[ScheduleModel]:
        """
        Intended to fire every ~30s by a clock driver.
        Finds due schedules, emits trigger command, recalculates next fire.
        Returns the list of fired schedules for the clock driver to track.
        """
        now = current_time or datetime.now(timezone.utc)
        
        # In a real deployed version, query limits and pagination should be used.
        due_schedules = await self.repo.get_due_schedules(now.timestamp())
        
        fired = []
        for schedule in due_schedules:
            if not schedule.is_active:
                continue
                
            # If the next_fire_at is missing, ignore it.
            if not schedule.next_fire_at:
                continue

            # Ensure we only fire once by advancing the fire time before queuing.
            schedule.next_fire_at = CronUtils.compute_next_fire(
                schedule.cron_expression, schedule.timezone, from_time=now
            )
            
            # The execution run logic (triggering actual DAG run) will be delegated to 
            # Celery workers processing the 'due' queue.
            # Here we just mark the schedule advanced.
            
            # Use a dummy tenant_id for scheduler batch ops if the repo isn't strictly partitioned, 
            # or rely on the repo having a `update_batch` or something. The protocol requires `tenant_id`
            # which is an implicit contract constraint from Phase 1. 
            tenant_id = getattr(schedule, "tenant_id", "system") # fallback handle
            await self.repo.update(tenant_id, schedule.schedule_id, schedule)
            
            fired.append(schedule)

        return fired
