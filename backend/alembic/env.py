"""Alembic environment: runs migrations with the app's async engine settings."""

import asyncio
import os

from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata

# `ALEMBIC_DATABASE_URL` lets the test suite and one-off scripts point
# migrations at a different database without touching the app's settings.
DATABASE_URL = os.environ.get("ALEMBIC_DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
