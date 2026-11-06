"""Tests for learned baseline + per-turn replay log (Phase 3 #2, Phase 3B #4)."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import CameraEvent, Device, User
from ownerai.services.baseline import (
    BaselineError,
    Deviation,
    evaluate_deviation,
    learn_baselines,
)
from ownerai.services.replay import ReplayLog


def _add_events(session, owner_id, device_id, base_time, counts_by_hour):
    """Insert CameraEvent rows at given hour offsets."""
    inserted = []
    for hour_offset, count in counts_by_hour.items():
        for _ in range(count):
            event = CameraEvent(
                device_id=device_id,
                owner_id=owner_id,
                kind="motion",
                summary="test event",
                confidence=0.9,
                occurred_at=base_time + timedelta(hours=hour_offset),
            )
            session.add(event)
            inserted.append(event)
    session.flush()
    return inserted


class TestBaselineFeatureFlag:
    def test_learn_disabled(self):
        with pytest.raises(BaselineError, match="not enabled"):
            learn_baselines(1)


class TestLearnBaseline:
    def test_learn_from_events(self, owner):
        os.environ["OWNERAI_FEATURE_LEARNED_BASELINE"] = "1"
        try:
            from ownerai.features import is_enabled
            assert is_enabled("LEARNED_BASELINE") is True

            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)
                device_id = device.id

                base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
                # 7 events all in the same hour-of-week bucket (same weekday+hour)
                for i in range(7):
                    _add_events(session, user.id, device_id, base + timedelta(minutes=i), {0: 1})
                session.commit()

                upserted = learn_baselines(user.id, days=7)
                assert upserted >= 1

                # Baseline: 1 event per bucket (7 days × 1 event at hour 10).
                # 1 event at same bucket -> within baseline, no deviation
                dev = evaluate_deviation(device_id, 1, base)
                assert dev is None

                # 5 events at same bucket -> deviation (baseline is flat at 1)
                dev = evaluate_deviation(device_id, 5, base)
                assert dev is not None
                assert isinstance(dev, Deviation)
                assert dev.observed == 5
                assert dev.z_score == float("inf")
                assert "events" in dev.explanation
        finally:
            os.environ.pop("OWNERAI_FEATURE_LEARNED_BASELINE", None)

    def test_no_baseline_returns_none(self, owner):
        os.environ["OWNERAI_FEATURE_LEARNED_BASELINE"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                device = Device(owner_id=user.id, name="Cam2")
                session.add(device)
                session.commit()
                session.refresh(device)
                device_id = device.id

                dev = evaluate_deviation(device_id, 100, datetime.now(timezone.utc))
                assert dev is None
        finally:
            os.environ.pop("OWNERAI_FEATURE_LEARNED_BASELINE", None)


class TestReplayLog:
    def test_record_disabled_returns_none(self):
        log = ReplayLog()
        assert log.record(owner_id=1, user_message="hi", intent="chat", tools_called=[], evidence_event_ids=[], answer="ok") is None
        assert log.list_turns(1) == []

    def test_record_enabled(self):
        os.environ["OWNERAI_FEATURE_REPLAY_LOG"] = "1"
        try:
            log = ReplayLog()
            turn_id = log.record(
                owner_id=1,
                user_message="who is at the door?",
                intent="camera_vision_scene",
                tools_called=[{"tool": "summarize_recent_events", "arguments": {}}],
                evidence_event_ids=[7, 8],
                answer="One person at the door.",
            )
            assert turn_id is not None and turn_id > 0

            turns = log.list_turns(1)
            assert len(turns) == 1
            assert turns[0]["user_message"] == "who is at the door?"
            assert turns[0]["intent"] == "camera_vision_scene"
            assert turns[0]["tools_called"][0]["tool"] == "summarize_recent_events"
            assert turns[0]["evidence_event_ids"] == [7, 8]
            assert turns[0]["answer"] == "One person at the door."
            assert "created_at" in turns[0]
        finally:
            os.environ.pop("OWNERAI_FEATURE_REPLAY_LOG", None)


class TestBaselineEndpoints:
    def test_learn_requires_flag(self, owner):
        resp = owner.post("/api/baseline/learn")
        assert resp.status_code == 403

    def test_learn_requires_auth(self, client):
        resp = client.post("/api/baseline/learn")
        assert resp.status_code == 401

    def test_learn_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_LEARNED_BASELINE"] = "1"
        try:
            resp = owner.post("/api/baseline/learn")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "LEARNED_BASELINE"
            assert "baselines_upserted" in data
        finally:
            os.environ.pop("OWNERAI_FEATURE_LEARNED_BASELINE", None)


class TestReplayEndpoints:
    def test_turns_requires_flag(self, owner):
        resp = owner.get("/api/replay/turns")
        assert resp.status_code == 403

    def test_turns_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_REPLAY_LOG"] = "1"
        try:
            resp = owner.get("/api/replay/turns")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "REPLAY_LOG"
            assert "turns" in data
        finally:
            os.environ.pop("OWNERAI_FEATURE_REPLAY_LOG", None)
