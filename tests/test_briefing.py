"""Tests for the overnight security briefing agent (Phase O-2)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import CameraEvent, Device, User
from ownerai.services.briefing import BriefingError, generate_briefing


def _make_event(
    session,
    owner_id: int,
    device_id: int,
    kind: str,
    summary: str,
    confidence: float,
    occurred_at: datetime,
) -> CameraEvent:
    event = CameraEvent(
        device_id=device_id,
        owner_id=owner_id,
        kind=kind,
        summary=summary,
        confidence=confidence,
        occurred_at=occurred_at,
    )
    session.add(event)
    session.flush()
    return event


class TestBriefingService:
    def test_briefing_disabled(self):
        os.environ.pop("OWNERAI_FEATURE_SECURITY_BRIEFING", None)
        with pytest.raises(BriefingError, match="not enabled"):
            generate_briefing(1)

    def test_empty_briefing(self, owner):
        os.environ["OWNERAI_FEATURE_SECURITY_BRIEFING"] = "1"
        try:
            briefing = generate_briefing(1)
            assert briefing.event_count == 0
            assert briefing.security_relevant_count == 0
            assert briefing.narrative != ""
            assert briefing.spoken_summary != ""
        finally:
            os.environ.pop("OWNERAI_FEATURE_SECURITY_BRIEFING", None)

    def test_security_relevant_events(self, owner):
        os.environ["OWNERAI_FEATURE_SECURITY_BRIEFING"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                device = Device(owner_id=user_id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)

                base = datetime.now(timezone.utc)
                _make_event(
                    session, user_id, device.id, "person", "person at door",
                    0.85, base - timedelta(hours=2)
                )
                _make_event(
                    session, user_id, device.id, "alert", "tamper detected",
                    0.9, base - timedelta(hours=1)
                )
                _make_event(
                    session, user_id, device.id, "note", "routine note",
                    0.5, base
                )
                session.commit()

            briefing = generate_briefing(user_id, period="daily")
            assert briefing.event_count == 3
            assert briefing.security_relevant_count == 2
            assert "person" in briefing.narrative.lower() or "events" in briefing.narrative.lower()
            assert "tamper" in briefing.narrative.lower() or "alert" in briefing.narrative.lower()
            assert briefing.spoken_summary != ""
            assert "Security briefing" in briefing.spoken_summary
        finally:
            os.environ.pop("OWNERAI_FEATURE_SECURITY_BRIEFING", None)


class TestBriefingEndpoints:
    def test_briefing_requires_flag(self, owner):
        resp = owner.get("/api/briefing/security")
        assert resp.status_code == 403

    def test_briefing_requires_auth(self, client):
        resp = client.get("/api/briefing/security")
        assert resp.status_code == 401

    def test_briefing_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_SECURITY_BRIEFING"] = "1"
        try:
            resp = owner.get("/api/briefing/security")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "SECURITY_BRIEFING"
            assert "narrative" in data
            assert "spoken_summary" in data
            assert "event_count" in data
        finally:
            os.environ.pop("OWNERAI_FEATURE_SECURITY_BRIEFING", None)
