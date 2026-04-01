"""
QuotaChecker - Enforces hard limits before triggering workflow runs.
"""
from __future__ import annotations

from datetime import datetime, timezone

from workflow_engine.errors import QuotaExceededError
from workflow_engine.models import TenantConfig
from workflow_engine.ports import BillingRepository


class QuotaChecker:
    """Verifies if a tenant has capacity to execute workflows."""

    # Soft defaults if no quotas explicitly set in TenantConfig
    DEFAULT_MONTHLY_RUNS = {
        "FREE": 100,
        "STARTER": 5_000,
        "PRO": 50_000,
        "ENTERPRISE": 1_000_000,
    }

    def __init__(self, billing_repo: BillingRepository) -> None:
        self._repo = billing_repo

    async def check_execution_quota(self, tenant: TenantConfig) -> None:
        """
        Verify the tenant has not exceeded their allowed monthly runs.
        
        Raises:
            QuotaExceededError: if out of monthly runs.
        """
        now = datetime.now(tz=timezone.utc)
        
        # 1. Determine limit
        limit = tenant.quotas.get("monthly_runs")
        if limit is None:
            # Fallback to tier default
            limit = self.DEFAULT_MONTHLY_RUNS.get(str(tenant.plan_tier.value), 100)
            
        # 2. Skip for infinite
        if limit < 0:
            return
            
        # 3. Fetch actual usage this month via PG count
        current_usage = await self._repo.get_monthly_run_count(
            tenant.tenant_id, 
            year=now.year, 
            month=now.month
        )
        
        if current_usage >= limit:
            raise QuotaExceededError(
                f"Monthly execution quota exceeded. Used: {current_usage}, Limit: {limit}. "
                "Please upgrade your plan or wait until the next billing cycle."
            )
