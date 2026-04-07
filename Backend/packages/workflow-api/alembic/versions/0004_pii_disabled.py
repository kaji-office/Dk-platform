"""Add DISABLED value to pii_policy enum

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-07

Adds the DISABLED value to the pii_policy PostgreSQL ENUM so it matches
the PIIPolicy enum in workflow_engine/models/tenant.py which already defines
DISABLED, SCAN_WARN, SCAN_MASK, SCAN_BLOCK.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_FILE = (
    Path(__file__).parents[4]
    / "infra" / "database" / "postgres" / "migrations" / "004_pii_disabled.sql"
)


def upgrade() -> None:
    # ALTER TYPE ADD VALUE cannot run inside a transaction in PG < 12.
    # op.execute() uses the current connection; for safety we use COMMIT/BEGIN
    # guards if needed. In PG 12+ this is safe without special handling.
    conn = op.get_bind()
    sql = _SQL_FILE.read_text(encoding="utf-8").strip()
    # Strip comment lines before executing
    statements = [
        line for line in sql.splitlines()
        if line.strip() and not line.strip().startswith("--")
    ]
    for stmt in statements:
        conn.execute(text(stmt))


def downgrade() -> None:
    # PostgreSQL does not support removing ENUM values directly.
    # To roll back: recreate the type without DISABLED (destructive — requires
    # casting all columns). Not implemented; raise to prevent accidental rollback.
    raise NotImplementedError(
        "Downgrading pii_policy ENUM is not supported. "
        "To remove DISABLED: recreate the type and cast all columns manually."
    )
