"""ORM declarative base (single MetaData for Alembic autogenerate)."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


async def create_all() -> None:
    """Create schema from metadata (dev/test convenience; Alembic owns prod)."""
    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..db import get_engine  # local import to avoid cycle
    engine: AsyncEngine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
