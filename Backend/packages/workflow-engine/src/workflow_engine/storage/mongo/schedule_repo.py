"""
MongoDB Implementation for ScheduleRepository.

Stores ScheduleModel documents.
Provides the atomic `get_due_schedules` to pull and fire Cron triggers based on `next_fire_at`.
"""
from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from workflow_engine.models import ScheduleModel
from workflow_engine.ports import ScheduleRepository


class MongoScheduleRepository(ScheduleRepository):
    """
    MongoDB backed Schedule repository.
    
    Args:
        db: The connected AsyncIOMotorDatabase instance.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["schedules"]

    async def get(self, tenant_id: str, schedule_id: str) -> ScheduleModel | None:
        """Fetch a specific schedule."""
        doc = await self._collection.find_one({"tenant_id": tenant_id, "schedule_id": schedule_id})
        if not doc:
            return None
            
        doc.pop("_id", None)
        return ScheduleModel.model_validate(doc)

    async def create(self, tenant_id: str, schedule: ScheduleModel) -> ScheduleModel:
        """Create a new schedule."""
        data = schedule.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        try:
            await self._collection.insert_one(data)
        except DuplicateKeyError as exc:
            raise ValueError(f"Schedule ID '{schedule.schedule_id}' already exists.") from exc
            
        return schedule

    async def update(self, tenant_id: str, schedule_id: str, schedule: ScheduleModel) -> ScheduleModel:
        """Update an existing schedule (useful for recording next fire time)."""
        data = schedule.model_dump(mode="json")
        data["tenant_id"] = tenant_id
        
        await self._collection.replace_one(
            {"tenant_id": tenant_id, "schedule_id": schedule_id},
            data,
            upsert=False
        )
        return schedule

    async def get_due_schedules(self, timestamp: float) -> list[ScheduleModel]:
        """
        Global query (across all tenants) to pull due heartbeat triggers.
        The worker daemon iterates over these to dispatch jobs.
        """
        # Active equals True AND next_fire_at is less than or equal to current tick
        query = {
            "is_active": True,
            "next_fire_at": {"$lte": timestamp}
        }
        
        cursor = self._collection.find(query)
        schedules = []
        async for doc in cursor:
            doc.pop("_id", None)
            schedules.append(ScheduleModel.model_validate(doc))
            
        return schedules
