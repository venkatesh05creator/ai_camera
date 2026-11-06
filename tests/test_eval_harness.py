"""Tests for the offline evaluation harness (Phase O-4)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from ownerai.db import get_engine
from ownerai.models import AssistantTurn, CameraEvent, Device, User
from ownerai.services.eval import evaluate_turns


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


def _make_turn(
    session,
    owner_id: int,
    user_message: str,
    intent: str,
    evidence_event_ids: list[int],
    answer: str,
) -> AssistantTurn:
    turn = AssistantTurn(
        owner_id=owner_id,
        user_message=user_message,
        intent=intent,
        tools_called_json="[]",
        evidence_event_ids_json=json.dumps(evidence_event_ids),
        answer=answer,
    )
    session.add(turn)
    session.flush()
    return turn


class TestEvalHarness:
    def test_empty_report(self, owner):
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            report = evaluate_turns(1)
            assert report.total_turns == 0
            assert report.grounded_turns == 0
            assert report.hallucination_count == 0
            assert report.grounding_accuracy == 0.0
            assert report.turns == []
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)

    def test_flag_disabled_raises(self):
        os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)
        from ownerai.services.eval import EvalError
        with pytest.raises(EvalError, match="not enabled"):
            evaluate_turns(1)

    def test_grounded_turn(self, owner):
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                device = Device(owner_id=user_id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)

                base = datetime.now(timezone.utc)
                event = _make_event(
                    session, user_id, device.id, "person",
                    "person at door", 0.85, base
                )
                turn = _make_turn(
                    session, user_id,
                    "who is at the door?",
                    "camera_vision_scene",
                    [event.id],
                    "One person is at the door, confidence 0.85.",
                )
                session.commit()
                turn_id = turn.id
                event_id = event.id

            report = evaluate_turns(user_id)
            assert report.total_turns == 1
            assert report.grounded_turns == 1
            assert report.hallucination_count == 0
            assert report.grounding_accuracy == 1.0
            t = report.turns[0]
            assert t.turn_id == turn_id
            assert t.grounded is True
            assert t.hallucination_risk in ("none", "low")
            assert len(t.evidence_events) == 1
            assert t.evidence_events[0]["id"] == event_id
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)

    def test_hallucinated_turn(self, owner):
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                device = Device(owner_id=user_id, name="Cam")
                session.add(device)
                session.commit()
                session.refresh(device)

                # Turn makes a visual claim with NO evidence events.
                _make_turn(
                    session, user_id,
                    "who is at the door?",
                    "camera_vision_scene",
                    [],
                    "I see a stranger at the door with high confidence.",
                )
                session.commit()

            report = evaluate_turns(user_id)
            assert report.total_turns == 1
            assert report.hallucination_count == 1
            assert report.grounding_accuracy == 0.0
            t = report.turns[0]
            assert t.grounded is False
            assert t.hallucination_risk == "high"
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)

    def test_missing_evidence_event(self, owner):
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                # Turn cites event #999 which does not exist.
                _make_turn(
                    session, user_id,
                    "who is there?",
                    "camera_vision_scene",
                    [999],
                    "Event #999 shows a person.",
                )
                session.commit()

            report = evaluate_turns(user_id)
            assert report.total_turns == 1
            assert report.hallucination_count == 1
            t = report.turns[0]
            assert t.grounded is False
            assert t.hallucination_risk == "high"
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)

    def test_no_evidence_ack_is_grounded(self, owner):
        """An answer that explicitly states no evidence is grounded honesty."""
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            with Session(get_engine()) as session:
                user = session.query(User).filter_by(id=1).first()
                user_id = user.id
                _make_turn(
                    session, user_id,
                    "who is at the door?",
                    "camera_vision_scene",
                    [],
                    "No live camera frame is available. I cannot see anyone.",
                )
                session.commit()

            report = evaluate_turns(user_id)
            assert report.total_turns == 1
            assert report.grounded_turns == 1
            assert report.hallucination_count == 0
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)


class TestEvalEndpoints:
    def test_report_requires_flag(self, owner):
        resp = owner.get("/api/eval/report")
        assert resp.status_code == 403

    def test_report_requires_auth(self, client):
        resp = client.get("/api/eval/report")
        assert resp.status_code == 401

    def test_report_enabled(self, owner):
        os.environ["OWNERAI_FEATURE_EVAL_HARNESS"] = "1"
        try:
            resp = owner.get("/api/eval/report")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["feature"] == "EVAL_HARNESS"
            assert "total_turns" in data
            assert "grounding_accuracy" in data
            assert "turns" in data
        finally:
            os.environ.pop("OWNERAI_FEATURE_EVAL_HARNESS", None)
