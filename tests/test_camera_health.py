"""Tests for camera tamper & health detection (Phase 3 item #5)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import numpy as np
import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine, session_scope
from ownerai.models import CameraHealthCheck, Device, User
from ownerai.services.health import check_frozen, probe_frame, run_health_check
from ownerai.settings import get_settings


def _make_frame(brightness: int = 128) -> np.ndarray:
    base = np.full((48, 48, 3), brightness, dtype=np.uint8)
    noise = np.random.default_rng(0).integers(0, 40, size=(48, 48, 3), dtype=np.uint8)
    return np.clip(base.astype(int) + noise.astype(int), 0, 255).astype(np.uint8)


class TestProbeFrame:
    def test_healthy_frame(self):
        result = probe_frame(_make_frame(150))
        assert result.status == "healthy"
        assert result.ok is True

    def test_blurry_frame(self):
        result = probe_frame(np.full((48, 48, 3), 100, dtype=np.uint8))
        assert result.status == "blurry"
        assert result.ok is False

    def test_low_light_frame(self):
        result = probe_frame(np.full((48, 48, 3), 10, dtype=np.uint8))
        assert result.status in ("low_light", "tampered")
        assert result.ok is False

    def test_tampered_frame(self):
        result = probe_frame(np.full((48, 48, 3), 5, dtype=np.uint8))
        assert result.status == "tampered"
        assert result.ok is False


class TestCheckFrozen:
    def test_fresh_stream_not_frozen(self):
        device = Device(id=1, owner_id=1, name="cam", last_seen_at=datetime.now(timezone.utc))
        assert check_frozen(device).status == "healthy"

    def test_stale_stream_frozen(self):
        old = datetime.now(timezone.utc) - timedelta(seconds=200)
        device = Device(id=1, owner_id=1, name="cam", last_seen_at=old)
        result = check_frozen(device)
        assert result.status == "frozen"
        assert result.ok is False

    def test_never_seen_is_frozen(self):
        device = Device(id=1, owner_id=1, name="cam", last_seen_at=None)
        assert check_frozen(device).status == "frozen"


class TestRunHealthCheck:
    def _owner_device(self, owner):
        """Return (session, user, device) for the owner's first device."""
        with Session(get_engine()) as session:
            user = session.query(User).filter_by(id=1).first()
            device = session.query(Device).filter_by(owner_id=user.id).first()
            if device is None:
                device = Device(owner_id=user.id, name="Test Cam", last_seen_at=datetime.now(timezone.utc))
                session.add(device)
                session.add(device)
                session.commit()
                session.refresh(device)
            return session, user, device

    def test_persists_health_check(self, owner):
        os.environ["OWNERAI_FEATURE_CAMERA_HEALTH"] = "1"
        try:
            from ownerai.features import is_enabled
            assert is_enabled("CAMERA_HEALTH") is True

            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                device = session.query(Device).filter_by(owner_id=user_id).first()
                if device is None:
                    device = Device(owner_id=user_id, name="Test Cam", last_seen_at=datetime.now(timezone.utc))
                    session.add(device)
                    session.commit()
                    session.refresh(device)
                device_id = device.id

                frame = _make_frame(150)
                report = run_health_check(device, frame=frame)
                assert report.device_id == device_id
                assert report.status in ("healthy", "degraded")

                from ownerai.models import CameraHealthCheck
                row = (
                    session.query(CameraHealthCheck)
                    .filter_by(device_id=device_id)
                    .order_by(CameraHealthCheck.checked_at.desc())
                    .first()
                )
            assert row is not None
            assert row.owner_id == user_id
        finally:
            os.environ.pop("OWNERAI_FEATURE_CAMERA_HEALTH", None)


class TestHealthEndpoints:
    def test_list_health_requires_auth(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 401

    def test_probe_requires_auth(self, client):
        resp = client.post("/api/health/probe", json={"device_id": 1})
        assert resp.status_code == 401

    def test_list_health_requires_flag(self, owner):
        """Authenticated but feature disabled -> 403."""
        resp = owner.get("/api/health")
        assert resp.status_code == 403

    def test_probe_requires_flag(self, owner):
        resp = owner.post("/api/health/probe", json={"device_id": 1})
        assert resp.status_code == 403

    def test_probe_owner_scoped(self, owner, make_client):
        os.environ["OWNERAI_FEATURE_CAMERA_HEALTH"] = "1"
        try:
            headers = {"X-CSRF-Token": owner.cookies.get("ownerai_csrf") or ""}

            from ownerai.db import get_engine
            from ownerai.models import Device, User

            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam", last_seen_at=datetime.now(timezone.utc))
                session.add(device)
                session.commit()
                session.refresh(device)
                did = device.id

            resp = owner.post(
                "/api/health/probe", json={"device_id": did}, headers=headers
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["device_id"] == did
            assert "status" in data

            # A different user cannot probe this device
            from tests.conftest import create_user, login

            create_user("intruder@example.test", role="viewer")
            c2 = make_client()
            c2.get("/")
            login(c2, "intruder@example.test")
            headers2 = {"X-CSRF-Token": c2.cookies.get("ownerai_csrf") or ""}
            resp2 = c2.post(
                "/api/health/probe", json={"device_id": did}, headers=headers2
            )
            assert resp2.status_code == 404, resp2.text
        finally:
            os.environ.pop("OWNERAI_FEATURE_CAMERA_HEALTH", None)
