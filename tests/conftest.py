"""Tests: package fixtures (isolated env per session)."""

from __future__ import annotations

import os
import pathlib
import tempfile

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="aegis-test-"))
os.environ.setdefault("OWNERAI_APP_ENV", "test")
os.environ.setdefault("OWNERAI_DATABASE_URL", f"sqlite+aiosqlite:///{(_TMP / 'aegis.db').as_posix()}")
os.environ.setdefault("OWNERAI_SECRET_KEY", "test-secret-key-that-is-long-enough-for-suite-0123456789")
os.environ.setdefault("OWNERAI_JSON_LOGS", "false")
os.environ.setdefault("OWNERAI_LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.config import get_settings  # noqa: E402
from backend.app.db import reset_engine  # noqa: E402


@pytest.fixture()
def settings():
    reset_engine()
    return get_settings()


@pytest.fixture()
def client(settings):
    from backend.app.main import create_app
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    reset_engine()
