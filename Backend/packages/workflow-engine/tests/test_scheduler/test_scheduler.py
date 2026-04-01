"""
Scheduler module testing suite.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from workflow_engine.models import ScheduleModel
from workflow_engine.ports import ScheduleRepository
from workflow_engine.scheduler.service import SchedulerService


class MockScheduleRepo(ScheduleRepository):
    def __init__(self):
        self.schedules = {}

    async def get(self, tenant_id: str, schedule_id: str) -> ScheduleModel | None:
        return self.schedules.get(schedule_id)

    async def create(self, tenant_id: str, schedule: ScheduleModel) -> ScheduleModel:
        self.schedules[schedule.schedule_id] = schedule
        return schedule

    async def update(self, tenant_id: str, schedule_id: str, schedule: ScheduleModel) -> ScheduleModel:
        self.schedules[schedule_id] = schedule
        return schedule

    async def get_due_schedules(self, timestamp: float) -> list[ScheduleModel]:
        return [
            s for s in self.schedules.values() 
            if s.is_active and s.next_fire_at and s.next_fire_at.timestamp() <= timestamp
        ]


@pytest.mark.asyncio
async def test_scheduler_register():
    repo = MockScheduleRepo()
    svc = SchedulerService(repo)
    
    # 0 9 * * * = 9am daily
    schedule = ScheduleModel(
        schedule_id="sch-1", workflow_id="wf-1", cron_expression="0 9 * * *", timezone="UTC"
    )
    
    created = await svc.register("t1", schedule)
    assert created.is_active is True
    assert created.next_fire_at is not None
    assert created.next_fire_at.hour == 9
    assert created.next_fire_at.minute == 0


@pytest.mark.asyncio
async def test_scheduler_deactivate():
    repo = MockScheduleRepo()
    svc = SchedulerService(repo)
    
    schedule = ScheduleModel(
        schedule_id="sch-1", workflow_id="wf-1", cron_expression="0 9 * * *", timezone="UTC"
    )
    await svc.register("t1", schedule)
    
    deactivated = await svc.deactivate("t1", "sch-1")
    assert deactivated.is_active is False
    assert deactivated.next_fire_at is None
    
    # Tick should ignore it
    fired = await svc.tick(datetime(2050, 1, 1, tzinfo=timezone.utc))
    assert len(fired) == 0


@pytest.mark.asyncio
async def test_scheduler_tick():
    repo = MockScheduleRepo()
    svc = SchedulerService(repo)
    
    # 0 9 * * * = 9am daily
    schedule = ScheduleModel(
        schedule_id="sch-1", workflow_id="wf-1", cron_expression="0 9 * * *", timezone="UTC"
    )
    # Freeze time precisely to 2025-01-01 08:00:00 UTC
    now_8am = datetime(2025, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
    
    created = await svc.register("t1", schedule, from_time=now_8am)
    # Verify next_fire_at is exactly 9am
    assert created.next_fire_at.hour == 9
        
    # Tick before due = nothing fired
    fired = await svc.tick(datetime(2025, 1, 1, 8, 30, 0, tzinfo=timezone.utc))
    assert len(fired) == 0
    
    # Tick after due = fires exactly once and advances
    now_after_9am = datetime(2025, 1, 1, 9, 30, 0, tzinfo=timezone.utc)
    fired = await svc.tick(now_after_9am)
    assert len(fired) == 1
    
    fired_sch = fired[0]
    # Check that next_fire_at has advanced to the next 9am
    # Since we ticked at 9:30am Jan 1, next is 9:00am Jan 2
    assert fired_sch.next_fire_at.day == 2
    assert fired_sch.next_fire_at.hour == 9
