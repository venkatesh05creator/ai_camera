"""Database engine, session factory and declarative base."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .settings import Settings, get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base class for every ORM model."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _engine_kwargs(settings: Settings) -> dict:
    kwargs: dict = {"echo": settings.sql_echo, "future": True}
    if settings.database_url.startswith("sqlite"):
        # check_same_thread=False is required because FastAPI serves requests
        # from a thread pool.  Access is still funnelled through SQLAlchemy.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
        if ":memory:" in settings.database_url:
            kwargs["poolclass"] = StaticPool
    else:  # pragma: no cover - exercised only with a real database server
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
        kwargs["pool_recycle"] = 1800
    return kwargs


def get_engine(settings: Settings | None = None) -> Engine:
    """Return (and lazily build) the process-wide engine."""
    global _engine, _session_factory
    if _engine is None:
        settings = settings or get_settings()
        settings.ensure_runtime_directories()
        _engine = create_engine(settings.database_url, **_engine_kwargs(settings))
        if settings.database_url.startswith("sqlite"):
            _register_sqlite_pragmas(_engine)
        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
        logger.info("database engine initialised", extra={"dsn": _redact_dsn(settings.database_url)})
    return _engine


def _register_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


def _redact_dsn(url: str) -> str:
    """Remove credentials from a database URL before logging it."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _, _, host = rest.rpartition("@")
    return f"{scheme}://***@{host}"


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return the session factory bound to the current engine."""
    get_engine(settings)
    if _session_factory is None:  # pragma: no cover - set by get_engine
        raise RuntimeError("the session factory was not initialised")
    return _session_factory


def reset_engine() -> None:
    """Dispose of the engine (used by the test-suite)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Context manager providing a transactional scope."""
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    """Create all tables (idempotent)."""
    from . import models  # noqa: F401  (ensure models are registered)

    settings = settings or get_settings()
    engine = get_engine(settings)
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
