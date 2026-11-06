"""Offline evaluation harness (OpenJarvis transplant, Phase O-4).

Measures grounding accuracy and detects hallucinated detections in JARVIS
assistant turns, built only from stored replay-log turns and event metadata.

Grounding rule (Principle 2): JARVIS may only state what the latest detector
output and frame prove.  Every visual claim must cite camera ID, timestamp and
frame freshness.  An answer that mentions a person/detection/confidence with no
supporting evidence event is a potential hallucination.

Ships behind the ``EVAL_HARNESS`` feature flag (opt-in, default off).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from ..db import session_scope
from ..features import is_enabled
from ..models import AssistantTurn, CameraEvent
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class EvalError(RuntimeError):
    """Raised when the eval harness cannot run."""


@dataclass
class TurnEval:
    """Evaluation result for a single assistant turn."""

    turn_id: int
    user_message: str
    intent: str
    answer: str
    evidence_event_ids: list[int]
    grounded: bool
    hallucination_risk: str  # "none" | "low" | "medium" | "high"
    reasons: list[str] = field(default_factory=list)
    evidence_events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_message": self.user_message,
            "intent": self.intent,
            "answer": self.answer,
            "evidence_event_ids": self.evidence_event_ids,
            "grounded": self.grounded,
            "hallucination_risk": self.hallucination_risk,
            "reasons": self.reasons,
            "evidence_events": self.evidence_events,
        }


@dataclass
class EvalReport:
    """Aggregated evaluation report."""

    total_turns: int
    grounded_turns: int
    hallucination_count: int
    grounding_accuracy: float  # 0..1
    turns: list[TurnEval]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_turns": self.total_turns,
            "grounded_turns": self.grounded_turns,
            "hallucination_count": self.hallucination_count,
            "grounding_accuracy": round(self.grounding_accuracy, 4),
            "turns": [t.to_dict() for t in self.turns],
            "generated_at": self.generated_at,
        }


# Detection-claim keywords that suggest the answer is making a visual claim.
_DETECTION_KEYWORDS = (
    "person", "people", "detected", "detection", "camera", "frame", "face",
    "enrolled", "stranger", "unknown", "at the", "in front", "doorway",
    "confidence", "verified",
)

# Phrases that explicitly acknowledge no evidence (these are grounded, not hallucinated).
_NO_EVIDENCE_PHRASES = (
    "no live frame", "no camera frame", "people = 0", "no people",
    "no detection", "not available", "offline", "no live", "no evidence",
    "cannot see", "unable to see", "no one", "nobody",
)


def _claims_detection(answer: str) -> bool:
    """Return True if the answer appears to make a visual/detection claim."""
    lower = answer.lower()
    return any(kw in lower for kw in _DETECTION_KEYWORDS)


def _acknowledges_no_evidence(answer: str) -> bool:
    """Return True if the answer explicitly states there is no evidence."""
    lower = answer.lower()
    return any(phrase in lower for phrase in _NO_EVIDENCE_PHRASES)


def _extract_cited_event_ids(answer: str) -> list[int]:
    """Extract event IDs referenced in the answer (e.g. 'event #7', '#8')."""
    ids: list[int] = []
    for m in re.finditer(r"(?:event|#)\s*(\d{1,6})", answer):
        try:
            ids.append(int(m.group(1)))
        except ValueError:
            continue
    return ids


def evaluate_turn(
    turn: dict[str, Any],
    db,
    *,
    settings: Optional[Settings] = None,
) -> TurnEval:
    """Evaluate a single assistant turn for grounding and hallucination risk."""
    settings = settings or get_settings()
    turn_id = int(turn["id"])
    user_message = str(turn.get("user_message", ""))
    intent = str(turn.get("intent", ""))
    answer = str(turn.get("answer", ""))
    evidence_ids = list(turn.get("evidence_event_ids") or [])

    reasons: list[str] = []
    evidence_events: list[dict[str, Any]] = []

    # Load the referenced evidence events from the database.
    for eid in evidence_ids:
        event = db.get(CameraEvent, eid)
        if event is None:
            reasons.append(f"evidence event #{eid} does not exist")
            continue
        evidence_events.append(
            {
                "id": event.id,
                "device_id": event.device_id,
                "kind": event.kind,
                "confidence": event.confidence,
                "occurred_at": event.occurred_at.isoformat(),
            }
        )

    makes_claim = _claims_detection(answer)
    no_evidence_ack = _acknowledges_no_evidence(answer)

    # Grounding determination.
    grounded = True
    risk = "none"

    if not makes_claim:
        # Conversational / non-visual answer - no visual claim to ground.
        grounded = True
        risk = "none"
    elif no_evidence_ack:
        # Explicitly states no evidence - grounded honesty.
        grounded = True
        risk = "none"
    elif not evidence_ids:
        # Makes a visual claim but cites no evidence events.
        grounded = False
        reasons.append("makes a visual claim with no cited evidence events")
        risk = "high"
    else:
        # Cites evidence - check that cited events exist and are relevant.
        missing = [r for r in reasons if "does not exist" in r]
        if missing:
            grounded = False
            risk = "high"
        else:
            # Has real evidence; mark grounded but note if claim is broad.
            grounded = True
            risk = "low"

    # Hallucination detection: answer mentions specific people/detections not in evidence.
    lower = answer.lower()
    for kw in ("person", "people", "face", "stranger", "enrolled"):
        if kw in lower and not evidence_ids and not no_evidence_ack:
            reasons.append(f"mentions '{kw}' with no supporting evidence")
            risk = "high"
            grounded = False
            break

    return TurnEval(
        turn_id=turn_id,
        user_message=user_message,
        intent=intent,
        answer=answer,
        evidence_event_ids=evidence_ids,
        grounded=grounded,
        hallucination_risk=risk,
        reasons=reasons,
        evidence_events=evidence_events,
    )


def evaluate_turns(
    owner_id: int,
    *,
    limit: int = 100,
    settings: Optional[Settings] = None,
) -> EvalReport:
    """Evaluate recent assistant turns for an owner.

    Returns an :class:`EvalReport` with grounding accuracy and hallucination
    count.  Built only from stored replay-log turns and event metadata.
    """
    if not is_enabled("EVAL_HARNESS"):
        raise EvalError("EVAL_HARNESS feature is not enabled")
    settings = settings or get_settings()

    with session_scope(settings) as db:
        rows = (
            db.execute(
                select(AssistantTurn)
                .where(AssistantTurn.owner_id == owner_id)
                .order_by(AssistantTurn.created_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            .scalars()
            .all()
        )
        turns = [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "user_message": r.user_message,
                "intent": r.intent,
                "tools_called": json.loads(r.tools_called_json or "[]"),
                "evidence_event_ids": json.loads(r.evidence_event_ids_json or "[]"),
                "answer": r.answer,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    eval_turns: list[TurnEval] = []
    with session_scope(settings) as db:
        for turn in turns:
            eval_turns.append(evaluate_turn(turn, db, settings=settings))

    total = len(eval_turns)
    grounded = sum(1 for t in eval_turns if t.grounded)
    hallucination_count = sum(
        1 for t in eval_turns if t.hallucination_risk == "high"
    )
    accuracy = (grounded / total) if total else 0.0

    return EvalReport(
        total_turns=total,
        grounded_turns=grounded,
        hallucination_count=hallucination_count,
        grounding_accuracy=accuracy,
        turns=eval_turns,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
