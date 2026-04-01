import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from workflow_engine.models import TenantConfig, PlanTier
from workflow_engine.events import EventBus, EventType
from workflow_engine.errors import QuotaExceededError

from workflow_engine.billing.cost_calculator import CostCalculator, LLMPricingRegistry
from workflow_engine.billing.quota_checker import QuotaChecker
from workflow_engine.billing.usage_recorder import UsageRecorder
from workflow_engine.billing.aggregator import BillingAggregator


# --- CostCalculator & LLMPricingRegistry Tests ---

def test_llm_pricing_registry_known_model():
    cost = LLMPricingRegistry.calculate_llm_cost("gpt-4-turbo", input_tokens=1_000_000, output_tokens=1_000_000)
    # gpt-4-turbo: 10 input, 30 output = 40.00
    assert cost == Decimal("40.00")

def test_llm_pricing_registry_unknown_fallback():
    cost = LLMPricingRegistry.calculate_llm_cost("some-new-model", input_tokens=2_000_000, output_tokens=0)
    # default: 0.50 input, 1.50 output per 1M -> 1.00 cost
    assert cost == Decimal("1.00")

def test_cost_calculator_compute_cost():
    # 10,000 ms = 10 sec. 256MB = 0.25 GB
    # GB-sec = 2.5
    # * 0.0000166667 = 0.00004166675
    cost = CostCalculator.calculate_compute_cost(10_000, 256)
    assert cost == Decimal("0.00004166675")

def test_cost_calculator_node_cost():
    assert CostCalculator.get_node_cost("standard") == Decimal("0.00001")
    assert CostCalculator.get_node_cost("llm") == Decimal("0.00002")


# --- QuotaChecker Tests ---

@pytest.mark.asyncio
async def test_quota_checker_enforces_limit():
    repo = AsyncMock()
    # Mocking that 100 runs were used this month
    repo.get_monthly_run_count.return_value = 100
    
    checker = QuotaChecker(repo)
    
    # 1. Custom strict quota logic (e.g., set to 1) -> Raises
    tenant1 = TenantConfig(tenant_id="t1", quotas={"monthly_runs": 1})
    with pytest.raises(QuotaExceededError, match="Monthly execution quota exceeded"):
        await checker.check_execution_quota(tenant1)
        
    # 2. Infinite quota (set to -1) -> Does not raise
    tenant_inf = TenantConfig(tenant_id="t3", quotas={"monthly_runs": -1})
    await checker.check_execution_quota(tenant_inf)
    
    # 3. Default tier limit
    tenant_free = TenantConfig(tenant_id="t4", plan_tier=PlanTier.FREE) # FREE is 100 runs.
    repo.get_monthly_run_count.return_value = 100
    with pytest.raises(QuotaExceededError):
        await checker.check_execution_quota(tenant_free)


# --- UsageRecorder Tests ---

@pytest.mark.asyncio
async def test_usage_recorder_node_completed():
    repo = AsyncMock()
    bus = EventBus() # Real or mock bus. We'll use a real one and await handlers manually.
    
    recorder = UsageRecorder(repo, bus)
    
    payload = {
        "tenant_id": "t1",
        "run_id": "r1",
        "node_id": "n1",
        "node_type": "llm",
        "started_at": 1000.0,
        "completed_at": 1001.5  # 1.5 seconds later
    }
    
    await recorder._on_node_completed(payload)
    
    repo.record_node_execution.assert_called_once_with(
        "t1", "r1", "n1", "llm", 1500  # 1500 ms duration
    )

@pytest.mark.asyncio
async def test_usage_recorder_llm_completed():
    repo = AsyncMock()
    bus = EventBus()
    recorder = UsageRecorder(repo, bus)
    
    payload = {
        "tenant_id": "t1",
        "run_id": "r1",
        "model": "gpt-4",
        "input_tokens": 100,
        "output_tokens": 200,
        "cost_usd": 0.05
    }
    
    await recorder._on_llm_usage(payload)
    
    repo.record_llm_tokens.assert_called_once_with(
        "t1", "r1", "gpt-4", 100, 200, 0.05
    )


# --- BillingAggregator Tests ---

@pytest.mark.asyncio
async def test_billing_aggregator_no_data():
    class MockPool:
        async def fetchrow(self, query, tenant_id, run_id):
            return None  # No records found
            
    repo = MagicMock()
    repo._pool = MockPool()
    
    aggregator = BillingAggregator(repo)
    usage = await aggregator.generate_run_invoice("t1", "r1")
    
    # Base charge should still exist
    assert usage.base_execution_charge > 0.0
    assert usage.llm_tokens_used == 0
    assert usage.compute_seconds == 0.0
    assert usage.node_charge == 0.0

@pytest.mark.asyncio
async def test_billing_aggregator_sums_data():
    class MockPool:
        async def fetchrow(self, query, tenant_id, run_id):
            if "llm_cost_records" in query:
                return {"total_llm_cost": 0.25, "total_tokens": 5000}
            if "node_exec_records" in query:
                return {"total_ms": 2500, "total_nodes": 3}
            return None
            
    repo = MagicMock()
    repo._pool = MockPool()
    
    aggregator = BillingAggregator(repo)
    usage = await aggregator.generate_run_invoice("t1", "r1")
    
    assert usage.llm_tokens_used == 5000
    assert usage.compute_seconds == 2.5   # 2500ms -> 2.5s
    # Three standard nodes
    assert usage.node_charge == 0.00003   # 3 * 0.00001
