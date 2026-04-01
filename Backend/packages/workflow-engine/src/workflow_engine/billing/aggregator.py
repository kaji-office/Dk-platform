"""
Billing aggregator - Computes unified UsageRecords for API serving.
"""
from __future__ import annotations

from workflow_engine.models import UsageRecord
from workflow_engine.storage.postgres.billing_repo import PostgresBillingRepository


class BillingAggregator:
    """Consolidates complex metrics into simple UsageRecord API responses."""

    def __init__(self, repo: PostgresBillingRepository) -> None:
        self._repo = repo

    async def generate_run_invoice(self, tenant_id: str, run_id: str) -> UsageRecord:
        """
        Aggregate all records for a specific run and compute total cost.
        Returns a simplified UsageRecord indicating everything billed to the tenant.
        """
        # Complex aggregations typically happen in SQL GROUP BY sum(),
        # For this prototype port, we query raw rows or fake the DB response logic
        # if the PostgresBillingRepository methods for fetching back aren't fully flushed contextually.
        
        # Abstracting SQL for `SELECT sum(cost_usd), sum(input_tokens+output_tokens) WHERE run_id = $1`
        query_llm = """
            SELECT COALESCE(SUM(cost_usd), 0) as total_llm_cost,
                   COALESCE(SUM(input_tokens + output_tokens), 0) as total_tokens
            FROM llm_cost_records
            WHERE tenant_id = $1 AND run_id = $2
        """
        
        query_compute = """
            SELECT COALESCE(SUM(duration_ms), 0) as total_ms,
                   COUNT(node_id) as total_nodes
            FROM node_exec_records
            WHERE tenant_id = $1 AND run_id = $2
        """
        
        llm_row = await self._repo._pool.fetchrow(query_llm, tenant_id, run_id)
        comp_row = await self._repo._pool.fetchrow(query_compute, tenant_id, run_id)
        
        llm_cost = float(llm_row["total_llm_cost"] if llm_row else 0)
        tokens = int(llm_row["total_tokens"] if llm_row else 0)
        
        total_ms = int(comp_row["total_ms"] if comp_row else 0)
        node_count = int(comp_row["total_nodes"] if comp_row else 0)
        
        # Pull standard node charges from CostCalculator
        from workflow_engine.billing.cost_calculator import CostCalculator
        node_charge = float(CostCalculator.get_node_cost("standard") * node_count)
        base_charge = float(CostCalculator.get_base_execution_cost())

        return UsageRecord(
            run_id=run_id,
            tenant_id=tenant_id,
            base_execution_charge=base_charge,
            node_charge=node_charge,
            llm_tokens_used=tokens,
            compute_seconds=total_ms / 1000.0,
            storage_mb=0.0, # Handled via S3 bucket size metrics normally
        )
