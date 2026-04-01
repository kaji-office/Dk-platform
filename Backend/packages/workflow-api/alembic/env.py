"""Alembic environment — async SQLAlchemy with asyncpg."""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# DB URL from environment — never hardcoded.
# Set POSTGRES_URL_ASYNCPG=postgresql+asyncpg://user:pass@host/db
DATABASE_URL = os.environ["POSTGRES_URL_ASYNCPG"]


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
        
def _run_migrations(sync_conn) -> None:
    context.configure(connection=sync_conn)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        await conn.run_sync(_run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
