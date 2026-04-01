from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleModel(BaseModel):
    schedule_id: str = Field(...)
    workflow_id: str = Field(...)
    cron_expression: str = Field(..., description="Standard Unix cron expression")
    timezone: str = Field(default="UTC")
    next_fire_at: datetime | None = None
    is_active: bool = Field(default=True)
