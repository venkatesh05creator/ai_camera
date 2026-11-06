"""Async SQLAlchemy engine + session factory (SQLite/aiosqlite by default).

SQLite hardening pragmas: WAL journaling, foreign keys ON, busy timeout.
The ``var/`` directory for a relative database path is created on demand.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import Settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def sqlite_file_path(database_url: str) -> Path | None:
    """Return the on-disk path for a sqlite URL (None for other dialects)."""
    if not database_url.startswith("sqlite"):
        return None
    url = make_url(database_url)
    db_file = url.database or ""
    if not db_file or db_file == ":memory:":
        return None
    path = Path(db_file)
    return path if path.is_absolute() else (Path.cwd() / path)


def build_engine(settings: Settings) -> AsyncEngine:
    path = sqlite_file_path(settings.database_url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(settings.database_url, echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
        if not settings.database_url.startswith("sqlite"):
            return
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        from .config import get_settings
        _engine = build_engine(settings or get_settings())
    if _session_factory is None:
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    if _session_factory is None:  # pragma: no cover - defensive
        raise RuntimeError("engine not initialized")
    return _session_factory


def reset_engine() -> None:
    """Dispose and forget the cached engine (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine = None
        _session_factory = None


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def check_database() -> dict[str, object]:
    """Real health check: run SELECT 1 and measure latency."""
    import time
    engine = get_engine()
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"reachable": True, "latency_ms": latency_ms}
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("database health check failed")
        return {"reachable": False, "error": type(exc).__name__}


async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context session for services (commit/rollback semantics)."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
