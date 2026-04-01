"""Alembic environment configuration."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read DB URL from environment (set by consumer — never hardcoded)
DATABASE_URL = os.environ["POSTGRES_URL_ASYNCPG"]


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        await conn.run_sync(context.configure)
        async with context.begin_transaction():
            await conn.run_sync(context.run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
