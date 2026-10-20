"""Shared pytest fixtures.

The environment is configured *before* the application package is imported so
that the settings singleton picks up the test configuration.  The database is
recreated for every test so that state (including rate-limit counters) never
leaks between tests.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / "ownerai_test.db"

os.environ["OWNERAI_APP_ENV"] = "test"
os.environ["OWNERAI_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-tests-0123456789"
os.environ["OWNERAI_BIOMETRIC_ENCRYPTION_KEY"] = "test-biometric-key-0123456789"
os.environ["OWNERAI_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["OWNERAI_MAILER_BACKEND"] = "null"
os.environ["OWNERAI_AI_PROVIDER"] = "offline"
os.environ["OWNERAI_RATE_LIMIT_ENABLED"] = "true"
os.environ["OWNERAI_LOGIN_RATE_LIMIT"] = "5"
os.environ["OWNERAI_LOGIN_RATE_WINDOW_SECONDS"] = "300"
os.environ["OWNERAI_REGISTER_RATE_LIMIT"] = "3"
os.environ["OWNERAI_TRUSTED_HOSTS"] = "testserver,localhost"
os.environ["OWNERAI_LOG_LEVEL"] = "WARNING"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from ownerai.db import Base, get_engine, reset_engine  # noqa: E402
from ownerai.main import create_app  # noqa: E402
from ownerai.models import Role, User  # noqa: E402
from ownerai.security import hash_password  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _engine():
    """Build the engine once for the session."""
    reset_engine()
    engine = get_engine()
    yield engine
    reset_engine()


@pytest.fixture(autouse=True)
def _fresh_database(_engine):
    """Recreate the schema before every test."""
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    yield


@pytest.fixture()
def app():
    """A fresh application instance per test."""
    return create_app()


@pytest.fixture()
def client(app):
    """A test client that already holds a CSRF cookie."""
    with TestClient(app, base_url="http://testserver") as test_client:
        test_client.get("/")
        yield test_client


@pytest.fixture()
def make_client(app):
    """Factory for additional, independent clients (one session per client)."""
    created = []

    def factory() -> TestClient:
        test_client = TestClient(app, base_url="http://testserver")
        test_client.get("/")
        created.append(test_client)
        return test_client

    yield factory

    for test_client in created:
        test_client.close()


def csrf(client: TestClient) -> str:
    """Return the CSRF token of the client."""
    return client.cookies.get("ownerai_csrf") or ""


def auth_headers(client: TestClient) -> dict:
    """Return the headers required for a state-changing request."""
    return {"X-CSRF-Token": csrf(client)}


def register(client: TestClient, email: str = "owner@example.test", password: str = "Correct-Horse-9!"):
    """Register a user and return the response payload."""
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
        headers=auth_headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str = "owner@example.test", password: str = "Correct-Horse-9!"):
    """Sign in and return the response payload."""
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers=auth_headers(client),
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_user(email: str = "user@example.test", password: str = "Correct-Horse-9!", role: str = Role.VIEWER.value) -> int:
    """Create a user directly in the database and return its id."""
    with Session(get_engine()) as session:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            role=role,
            email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return int(user.id)


@pytest.fixture()
def owner(make_client):
    """The first registered account - the owner of the installation."""
    client = make_client()
    register(client)
    login(client)
    return client


@pytest.fixture()
def viewer(make_client):
    """A regular, read-only account."""
    client = make_client()
    create_user("viewer@example.test", role=Role.VIEWER.value)
    login(client, "viewer@example.test")
    return client


@pytest.fixture()
def trusted(make_client):
    """A trusted user of the installation."""
    client = make_client()
    create_user("trusted@example.test", role=Role.TRUSTED.value)
    login(client, "trusted@example.test")
    return client


@pytest.fixture()
def admin_user(make_client):
    """An administrator of the installation."""
    client = make_client()
    create_user("admin@example.test", role=Role.ADMIN.value)
    login(client, "admin@example.test")
    return client
