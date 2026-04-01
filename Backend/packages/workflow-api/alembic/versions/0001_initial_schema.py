"""Initial database schema

Revision ID: 0001
Revises:
Create Date: 2026-03-31

Wraps infra/database/postgres/migrations/001_initial_schema.sql.
Alembic tracks whether this has been applied via the alembic_version table,
so re-running `alembic upgrade head` on a database that already has the schema
is safe — Alembic skips already-applied revisions.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Locate the SQL file relative to this versions/ directory.
# Resolves to: infra/database/postgres/migrations/001_initial_schema.sql
_SQL_FILE = (
    Path(__file__).parents[4]
    / "infra" / "database" / "postgres" / "migrations" / "001_initial_schema.sql"
)


def _split_sql(sql: str) -> list[str]:
    """Split SQL on semicolons while respecting dollar-quoted strings (PL/pgSQL).

    A naive split(";") breaks on function bodies like:
        CREATE FUNCTION ... AS $$ BEGIN ... ; END; $$ LANGUAGE plpgsql;
    This parser tracks whether we're inside a $$...$$  block and only splits
    on semicolons that appear outside of one.
    """
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    in_dollar_quote = False
    dollar_tag = ""

    while i < len(sql):
        # Detect dollar-quote open/close tag (e.g. $$ or $tag$)
        dq_match = re.match(r"\$([^$]*)\$", sql[i:])
        if dq_match:
            tag = dq_match.group(0)
            if not in_dollar_quote:
                in_dollar_quote = True
                dollar_tag = tag
            elif tag == dollar_tag:
                in_dollar_quote = False
                dollar_tag = ""
            buf.append(tag)
            i += len(tag)
            continue

        ch = sql[i]
        if ch == ";" and not in_dollar_quote:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1

    # Trailing statement with no final semicolon
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)

    return statements


def upgrade() -> None:
    sql = _SQL_FILE.read_text(encoding="utf-8")
    conn = op.get_bind()
    for stmt in _split_sql(sql):
        conn.execute(text(stmt))


def downgrade() -> None:
    # Full schema teardown — destructive, only for local dev reset.
    op.execute("""
        DROP TABLE IF EXISTS
            password_reset_tokens,
            semantic_cache,
            tenant_usage_summary,
            node_exec_records,
            llm_cost_records,
            api_keys,
            oauth_tokens,
            users,
            tenants
        CASCADE;
        DROP TYPE IF EXISTS plan_tier, isolation_model, user_role, pii_policy CASCADE;
        DROP EXTENSION IF EXISTS vector;
        DROP EXTENSION IF EXISTS pgcrypto;
        DROP EXTENSION IF EXISTS "uuid-ossp";
    """)
