"""
Postgres implementations for relational domain objects.
"""
from __future__ import annotations

import json
from typing import Any

from asyncpg import Pool

from workflow_engine.models import UserModel
from workflow_engine.ports import UserRepository


class PostgresUserRepository(UserRepository):
    """
    PostgreSQL backed UserRepository using asyncpg.
    
    Args:
        pool: An active asyncpg connection pool.
    """

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def get(self, user_id: str) -> UserModel | None:
        """Fetch a user by ID."""
        query = "SELECT id, email, role, mfa_enabled FROM users WHERE id = $1"
        row = await self._pool.fetchrow(query, user_id)
        
        if not row:
            return None
            
        return self._map_row(row)

    async def get_by_email(self, email: str) -> UserModel | None:
        """Fetch a user by normalized email."""
        query = "SELECT id, email, role, mfa_enabled FROM users WHERE email = $1"
        row = await self._pool.fetchrow(query, email.lower())
        
        if not row:
            return None
            
        return self._map_row(row)

    def _map_row(self, row: dict[str, Any]) -> UserModel:
        """Convert a postgres row dict into the UserModel."""
        return UserModel(
            id=str(row["id"]),
            email=row["email"],
            role=row["role"],
            mfa_enabled=row["mfa_enabled"],
        )

    async def get_by_id(self, user_id: str) -> UserModel | None:
        """Alias for get() to match GDPR handler expectations."""
        return await self.get(user_id)

    async def delete(self, user_id: str) -> bool:
        """Hard-delete a user record (GDPR Right to Erasure)."""
        query = "DELETE FROM users WHERE id = $1 RETURNING id"
        row = await self._pool.fetchrow(query, user_id)
        return row is not None

    async def create_user(self, tenant_id: str, user_data: dict[str, Any]) -> UserModel:
        """Insert a new user row and return the mapped model."""
        query = """
            INSERT INTO users (id, tenant_id, email, password_hash, role, is_verified)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, email, role, mfa_enabled
        """
        row = await self._pool.fetchrow(
            query,
            user_data["id"],
            tenant_id,
            user_data["email"],
            user_data.get("password_hash"),
            user_data.get("role", "VIEWER"),
            user_data.get("is_verified", False),
        )
        return self._map_row(row)

    async def update_user(self, tenant_id: str, user_id: str, payload: dict[str, Any]) -> UserModel:
        """Update allowed user fields and return the updated model."""
        allowed = {"email", "password_hash", "role", "is_verified", "mfa_enabled", "mfa_secret"}
        fields = {k: v for k, v in payload.items() if k in allowed}
        if not fields:
            row = await self._pool.fetchrow(
                "SELECT id, email, role, mfa_enabled FROM users WHERE id = $1 AND tenant_id = $2",
                user_id, tenant_id,
            )
            return self._map_row(row)

        set_clause = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(fields))
        values = list(fields.values())
        query = f"""
            UPDATE users SET {set_clause}
            WHERE id = $1 AND tenant_id = $2
            RETURNING id, email, role, mfa_enabled
        """
        row = await self._pool.fetchrow(query, user_id, tenant_id, *values)
        return self._map_row(row)

    async def list_users(self, tenant_id: str, skip: int = 0, limit: int = 50) -> list[UserModel]:
        """List users for a tenant."""
        query = """
            SELECT id, email, role, mfa_enabled FROM users
            WHERE tenant_id = $1
            ORDER BY email
            OFFSET $2 LIMIT $3
        """
        rows = await self._pool.fetch(query, tenant_id, skip, limit)
        return [self._map_row(r) for r in rows]
