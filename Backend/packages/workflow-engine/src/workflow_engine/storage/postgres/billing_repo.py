"""
Postgres implementation for Billing metrics and token records.
"""
from __future__ import annotations

from typing import Any

from asyncpg import Pool


class PostgresBillingRepository:
    """
    PostgreSQL backed Billing and Usage storage using asyncpg.
    
    Args:
        pool: An active asyncpg connection pool.
    """

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def record_llm_tokens(
        self,
        tenant_id: str,
        run_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float
    ) -> None:
        """Insert a token usage record."""
        query = """
            INSERT INTO llm_cost_records
            (tenant_id, run_id, model_name, input_tokens, output_tokens, cost_usd)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        await self._pool.execute(
            query,
            tenant_id,
            run_id,
            model,
            input_tokens,
            output_tokens,
            cost_usd
        )

    async def record_node_execution(
        self,
        tenant_id: str,
        run_id: str,
        node_id: str,
        node_type: str,
        duration_ms: int
    ) -> None:
        """Insert a node execution duration record."""
        query = """
            INSERT INTO node_exec_records
            (tenant_id, run_id, node_id, node_type, duration_ms)
            VALUES ($1, $2, $3, $4, $5)
        """
        await self._pool.execute(
            query,
            tenant_id,
            run_id,
            node_id,
            node_type,
            duration_ms
        )

    async def get_monthly_run_count(self, tenant_id: str, year: int, month: int) -> int:
        """Count unique runs triggered by a tenant in a calendar month."""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year+1}-01-01"
        else:
            end_date = f"{year}-{month+1:02d}-01"
            
        # We rely on node_exec_records to approximate "runs" assuming they execute at least one node
        query = """
            SELECT COUNT(DISTINCT run_id)
            FROM node_exec_records
            WHERE tenant_id = $1 AND timestamp >= $2::timestamp AND timestamp < $3::timestamp
        """
        val = await self._pool.fetchval(query, tenant_id, start_date, end_date)
        return val or 0
