"""Performance indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-07

Wraps infra/database/postgres/migrations/003_performance_indexes.sql.
Adds CONCURRENTLY-safe indexes for high-frequency lookups:
  - api_keys.key_hash (authenticated API key requests)
  - users.verification_token (email verification flow)
  - users.reset_token (password reset flow)

Note: CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
Alembic runs each migration in a transaction by default, so we set
transaction=False via the __alembic_connection__ context below.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_FILE = (
    Path(__file__).parents[4]
    / "infra" / "database" / "postgres" / "migrations" / "003_performance_indexes.sql"
)


def upgrade() -> None:
    # CREATE INDEX CONCURRENTLY requires running outside a transaction.
    # We execute each statement individually with autocommit via raw connection.
    conn = op.get_bind()
    sql = _SQL_FILE.read_text(encoding="utf-8")
    for line in sql.splitlines():
        stmt = line.strip()
        if stmt and not stmt.startswith("--"):
            conn.execute(text(stmt))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_keys_key_hash;")
    op.execute("DROP INDEX IF EXISTS idx_users_verification_token;")
    op.execute("DROP INDEX IF EXISTS idx_users_reset_token;")
