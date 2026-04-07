"""Webhooks schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-07

Wraps infra/database/postgres/migrations/002_webhooks.sql.
Creates the `webhooks` and `webhook_deliveries` tables.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SQL_FILE = (
    Path(__file__).parents[4]
    / "infra" / "database" / "postgres" / "migrations" / "002_webhooks.sql"
)


def _split_sql(sql: str) -> list[str]:
    """Split SQL on semicolons while respecting dollar-quoted strings."""
    statements: list[str] = []
    buf: list[str] = []
    i = 0
    in_dollar_quote = False
    dollar_tag = ""

    while i < len(sql):
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
    op.execute("""
        DROP TABLE IF EXISTS webhook_deliveries CASCADE;
        DROP TABLE IF EXISTS webhooks CASCADE;
    """)
