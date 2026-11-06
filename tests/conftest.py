"""Tests: package fixtures (fresh DB per test)."""

from __future__ import annotations

import os

os.environ.setdefault("OWNERAI_APP_ENV", "test")
os.environ.setdefault("OWNERAI_SECRET_KEY", "test-secret-key-that-is-long-enough-for-suite-0123456789")
os.environ.setdefault("OWNERAI_JSON_LOGS", "false")
os.environ.setdefault("OWNERAI_LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402
from backend.app.db import reset_engine  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_global_state():
    from backend.app import globals as app_globals
    app_globals.reset_panic()
    yield
    app_globals.reset_panic()


@pytest.fixture()
def settings(tmp_path):
    """Fresh database file per test -> full isolation."""
    reset_engine()
    os.environ["OWNERAI_DATABASE_URL"] = (
        f"sqlite+aiosqlite:///{(tmp_path / 'aegis.db').as_posix()}"
    )
    return get_settings()


@pytest.fixture()
def client(settings):
    from backend.app.main import create_app
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    reset_engine()
