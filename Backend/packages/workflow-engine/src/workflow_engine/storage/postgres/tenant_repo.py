"""
Postgres implementation for TenantRepository.
"""
from __future__ import annotations

import json
from typing import Any

from asyncpg import Pool

from workflow_engine.models import TenantConfig
from workflow_engine.ports import TenantRepository


class PostgresTenantRepository(TenantRepository):
    """
    PostgreSQL backed TenantRepository using asyncpg.
    
    Args:
        pool: An active asyncpg connection pool.
    """

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def get(self, tenant_id: str) -> TenantConfig | None:
        """Fetch tenant config by ID."""
        query = "SELECT id, config_json FROM tenants WHERE id = $1"
        row = await self._pool.fetchrow(query, tenant_id)
        
        if not row:
            return None
            
        data = row["config_json"]
        if isinstance(data, str):
            data = json.loads(data)
            
        return TenantConfig.model_validate(data)

    async def create(self, tenant: TenantConfig) -> TenantConfig:
        """Create a new tenant record."""
        data = tenant.model_dump(mode="json")
        query = "INSERT INTO tenants (id, config_json) VALUES ($1, $2) RETURNING id"
        await self._pool.execute(query, tenant.tenant_id, json.dumps(data))
        return tenant

    async def update(self, tenant_id: str, tenant: TenantConfig) -> TenantConfig:
        """Replace the tenant config JSON block."""
        data = tenant.model_dump(mode="json")
        query = "UPDATE tenants SET config_json = $1 WHERE id = $2"
        await self._pool.execute(query, json.dumps(data), tenant_id)
        return tenant
