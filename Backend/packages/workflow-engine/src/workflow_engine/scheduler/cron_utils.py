"""Scheduler cron utilities."""
from datetime import datetime, timezone

from croniter import croniter  # type: ignore[import-untyped]
import pytz


class CronUtils:
    """Utilities for parsing cron rules with timezone support."""
    
    @staticmethod
    def compute_next_fire(cron_expr: str, tz_name: str = "UTC", from_time: datetime | None = None) -> datetime:
        """Computes the exact next trigger time for a cron, respecting DST edges."""
        if not croniter.is_valid(cron_expr):
            raise ValueError(f"Invalid cron expression: '{cron_expr}'")
            
        tz = pytz.timezone(tz_name)
        
        # All tracking done internally via UTC, localize to tz to compute cron edges
        now = from_time or datetime.now(timezone.utc)
        local_now = now.astimezone(tz)
        
        # Compute next occurrence in localized time
        cron = croniter(cron_expr, local_now)
        next_local = cron.get_next(datetime)
        
        # Convert back to UTC boundary
        # Using localize properly for edge cases or astimezone
        utc_next = tz.localize(next_local) if not next_local.tzinfo else next_local
        return utc_next.astimezone(timezone.utc)
