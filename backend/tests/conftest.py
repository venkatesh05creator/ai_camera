"""Pytest fixtures for backend integration testing."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use a temporary SQLite database for tests
temp_dir = tempfile.mkdtemp()
test_db_path = Path(temp_dir) / "test_surveillance.db"

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-privacy-surveillance-system-998877"
os.environ["BIOMETRIC_ENCRYPTION_KEY"] = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
os.environ["MEDIA_STORAGE_PATH"] = str(Path(temp_dir) / "media")
os.environ["SNAPSHOT_STORAGE_PATH"] = str(Path(temp_dir) / "snapshots")

from backend.app.core.database import Base, get_db
from backend.app.core.security import create_access_token, hash_password
from backend.app.main import create_app
from backend.app.models.entities import Camera, Person, User
from backend.app.services.consent_service import grant_consent

test_engine = create_engine(
    f"sqlite:///{test_db_path.as_posix()}",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_admin_user(db_session):
    user = db_session.query(User).filter_by(email="testadmin@example.com").first()
    if not user:
        user = User(
            email="testadmin@example.com",
            password_hash=hash_password("AdminSecurePassword123!"),
            display_name="Test Administrator",
            role="owner",
            status="active",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def test_viewer_user(db_session):
    user = db_session.query(User).filter_by(email="viewer@example.com").first()
    if not user:
        user = User(
            email="viewer@example.com",
            password_hash=hash_password("ViewerPassword123!"),
            display_name="Test Viewer",
            role="viewer",
            status="active",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(test_admin_user):
    return create_access_token(
        data={"sub": test_admin_user.id, "role": test_admin_user.role, "email": test_admin_user.email}
    )


@pytest.fixture
def viewer_token(test_viewer_user):
    return create_access_token(
        data={"sub": test_viewer_user.id, "role": test_viewer_user.role, "email": test_viewer_user.email}
    )


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}
