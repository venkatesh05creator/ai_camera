"""Alembic environment (async, driven by OWNERAI_DATABASE_URL).

Used for production/dev upgrades: ``.venv/Scripts/python.exe -m alembic upgrade head``
The schema it manages must always match ``backend.app.models.Base.metadata``.
"""

from __future__ import annotations

import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# make sure the repo root is importable regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import models as models_pkg  # noqa: F401 - registers tables
from backend.app.config import get_settings
from backend.app.models.base import Base

config = context.config

if config.config_file_name is not None:
    from logging.config import fileConfig
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    url = get_settings().database_url
    if url.startswith("sqlite:///") and "aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    import asyncio
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
