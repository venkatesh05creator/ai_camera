"""Overnight security briefing agent (OpenJarvis transplant, Phase O-2).

Generates a spoken + written narrative summary of stored camera events,
built only from event metadata (never raw frames, never stranger
identification).  External integrations (e.g. Gmail/Calendar briefings via
read-only OAuth) are opt-in and not part of this core.

Ships behind the ``SECURITY_BRIEFING`` feature flag (opt-in, default off).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from ..db import session_scope
from ..features import is_enabled
from ..models import CameraEvent
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class BriefingError(RuntimeError):
    """Raised when a briefing cannot be generated."""


@dataclass
class Briefing:
    """A security briefing built from stored events."""

    owner_id: int
    period: str  # daily | weekly
    started_at: datetime
    ended_at: datetime
    narrative: str
    spoken_summary: str  # short, TTS-friendly rendering
    event_count: int
    security_relevant_count: int
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "period": self.period,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "narrative": self.narrative,
            "spoken_summary": self.spoken_summary,
            "event_count": self.event_count,
            "security_relevant_count": self.security_relevant_count,
            "created_at": self.created_at.isoformat(),
        }


# Event kinds treated as security-relevant for the briefing.
_SECURITY_KINDS = {"alert", "person", "device_status", "tamper", "motion"}


def _kind_label(kind: str) -> str:
    return {
        "motion": "motion",
        "person": "person detected",
        "sound": "sound",
        "device_status": "device status change",
        "tamper": "tamper alert",
        "alert": "alert",
        "note": "note",
    }.get(kind, kind)


def generate_briefing(
    owner_id: int,
    period: str = "daily",
    *,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    settings: Optional[Settings] = None,
) -> Briefing:
    """Generate a narrative security briefing for a time window.

    Built only from stored CameraEvent metadata - never raw frames, never
    stranger identification.  Idempotent per (owner, period, window).
    """
    if not is_enabled("SECURITY_BRIEFING"):
        raise BriefingError("SECURITY_BRIEFING feature is not enabled")
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)

    if started_at is None:
        started_at = now - timedelta(days=1 if period == "daily" else 7)
    if ended_at is None:
        ended_at = now
    for attr in ("started_at", "ended_at"):
        val = locals()[attr]
        if val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)

    with session_scope(settings) as db:
        rows = (
            db.execute(
                select(CameraEvent)
                .where(CameraEvent.owner_id == owner_id)
                .where(CameraEvent.occurred_at >= started_at)
                .where(CameraEvent.occurred_at <= ended_at)
                .order_by(CameraEvent.occurred_at.asc())
            )
            .scalars()
            .all()
        )

    total = len(rows)
    security_events = [e for e in rows if e.kind in _SECURITY_KINDS]
    by_kind: dict[str, int] = {}
    by_device: dict[int, int] = {}
    for event in security_events:
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
        by_device[event.device_id] = by_device.get(event.device_id, 0) + 1

    parts: list[str] = []
    period_word = "past 24 hours" if period == "daily" else "past 7 days"
    if total == 0:
        parts.append(f"No camera events were recorded in the {period_word}.")
    else:
        parts.append(
            f"In the {period_word}, {total} camera events were recorded, "
            f"of which {len(security_events)} are security-relevant."
        )
        if by_kind:
            kind_parts = "; ".join(
                f"{c} {_kind_label(k)}" for k, c in sorted(by_kind.items(), key=lambda kv: -kv[1])
            )
            parts.append(f"Breakdown: {kind_parts}.")
        if by_device:
            top_device = max(by_device, key=by_device.get)
            parts.append(
                f"The most active camera was device #{top_device} "
                f"with {by_device[top_device]} security-relevant events."
            )

    narrative = " ".join(parts)
    spoken = (
        f"Security briefing for the {period_word}. "
        f"{total} events recorded, {len(security_events)} security-relevant. "
        + narrative
    )

    return Briefing(
        owner_id=owner_id,
        period=period,
        started_at=started_at,
        ended_at=ended_at,
        narrative=narrative,
        spoken_summary=spoken,
        event_count=total,
        security_relevant_count=len(security_events),
        created_at=datetime.now(timezone.utc),
    )
