"""Tests for privacy zones (Phase 3 #4) and digest (Phase 3 #6)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import CameraEvent, Device, Digest, PrivacyZone, User
from ownerai.services.digest import generate_digest
from ownerai.services.zones import blur_non_enrolled_faces, is_in_privacy_zone, point_in_polygon


class TestZonesService:
    def test_point_in_polygon(self):
        square = [[0, 0], [0, 1], [1, 1], [1, 0]]
        assert point_in_polygon((0.5, 0.5), square) is True
        assert point_in_polygon((2, 2), square) is False
        assert point_in_polygon((0.5, -0.1), square) is False

    def test_is_in_zone_disabled(self):
        assert is_in_privacy_zone(0.5, 0.5, 1) is False

    def test_blur_disabled_by_default(self):
        assert blur_non_enrolled_faces() is False


class TestZonesEndpoints:
    def test_zone_requires_flag(self, owner):
        resp = owner.post(
            "/api/privacy-zones",
            json={"device_id": 1, "name": "z", "polygon": [[0, 0], [0, 1], [1, 1]]},
        )
        assert resp.status_code == 403

    def test_zone_crud(self, owner):
        os.environ["OWNERAI_FEATURE_PRIVACY_ZONES"] = "1"
        try:
            # Need a device
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)
                did = device.id

            resp = owner.post(
                "/api/privacy-zones",
                json={"device_id": did, "name": "bedroom", "polygon": [[0, 0], [0, 1], [1, 1], [1, 0]]},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["name"] == "bedroom"
            assert len(data["polygon"]) == 4
            zid = data["id"]

            # List
            resp2 = owner.get("/api/privacy-zones")
            assert resp2.status_code == 200
            assert len(resp2.json()["zones"]) == 1

            # Delete
            resp3 = owner.delete(f"/api/privacy-zones/{zid}")
            assert resp3.status_code == 200

            resp4 = owner.get("/api/privacy-zones")
            assert len(resp4.json()["zones"]) == 0
        finally:
            os.environ.pop("OWNERAI_FEATURE_PRIVACY_ZONES", None)


class TestDigestService:
    def test_digest_disabled(self):
        with pytest.raises(Exception, match="not enabled"):
            generate_digest(1)

    def test_generate_digest(self, owner):
        os.environ["OWNERAI_FEATURE_DIGEST"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                device = Device(owner_id=user_id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)

                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone.utc)
                for i in range(3):
                    event = CameraEvent(
                        device_id=device.id,
                        owner_id=user_id,
                        kind="person",
                        summary=f"event {i}",
                        confidence=0.9,
                        occurred_at=now - timedelta(hours=i),
                    )
                    session.add(event)
                session.commit()

            assert user_id is not None
            digest = generate_digest(user_id, period="daily")
            assert digest.event_count == 3
            assert digest.narrative != ""
        finally:
            os.environ.pop("OWNERAI_FEATURE_DIGEST", None)


class TestDigestEndpoints:
    def test_digest_requires_flag(self, owner):
        resp = owner.post("/api/digest", params={"period": "daily"})
        assert resp.status_code == 403

    def test_digest_create_and_get(self, owner):
        os.environ["OWNERAI_FEATURE_DIGEST"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam")
                session.add(device)
                session.commit()

            resp = owner.post("/api/digest", params={"period": "daily"})
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "DIGEST"
            assert "narrative" in data

            resp2 = owner.get("/api/digest", params={"period": "daily"})
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert data2["feature"] == "DIGEST"
        finally:
            os.environ.pop("OWNERAI_FEATURE_DIGEST", None)
