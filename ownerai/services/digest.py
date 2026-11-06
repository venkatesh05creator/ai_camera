"""Daily/weekly narrative digest built only from stored events (Phase 3 item #6).

Generates a short narrative summary of what happened, built only from stored
CameraEvent metadata - never raw frames, never stranger identification.
Ships behind the ``DIGEST`` feature flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from ..db import session_scope
from ..features import is_enabled
from ..models import CameraEvent, Digest
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class DigestError(RuntimeError):
    """Raised when a digest cannot be generated."""


def _kind_label(kind: str) -> str:
    return {
        "motion": "motion",
        "person": "person detected",
        "sound": "sound",
        "device_status": "device status change",
        "note": "note",
        "alert": "alert",
    }.get(kind, kind)


def generate_digest(
    owner_id: int,
    period: str = "daily",
    *,
    started_at: Optional[datetime] = None,
    ended_at: Optional[datetime] = None,
    settings: Optional[Settings] = None,
) -> Digest:
    """Generate a narrative digest for a time window.

    Returns the created :class:`Digest` row.  Idempotent per (owner, period,
    window) - replaces any existing digest for the same window.
    """
    if not is_enabled("DIGEST"):
        raise DigestError("DIGEST feature is not enabled")
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)

    if started_at is None:
        started_at = now - timedelta(days=1 if period == "daily" else 7)
    if ended_at is None:
        ended_at = now
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=timezone.utc)

    with session_scope(settings) as db:
        rows = (
            db.execute(
                select(CameraEvent)
                .where(CameraEvent.owner_id == owner_id)
                .where(CameraEvent.occurred_at >= started_at)
                .where(CameraEvent.occurred_at <= ended_at)
                .order_by(CameraEvent.occurred_at.asc())
                .limit(settings.digest_summary_max_events)
            )
            .scalars()
            .all()
        )

    total = len(rows)
    by_kind: dict[str, int] = {}
    by_device: dict[int, int] = {}
    peak_hour: Optional[int] = None
    peak_count = 0
    hour_counts: dict[int, int] = {}

    for event in rows:
        by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
        by_device[event.device_id] = by_device.get(event.device_id, 0) + 1
        h = event.occurred_at.hour
        hour_counts[h] = hour_counts.get(h, 0) + 1
        if hour_counts[h] > peak_count:
            peak_count = hour_counts[h]
            peak_hour = h

    parts: list[str] = []
    period_word = "24 hours" if period == "daily" else "7 days"
    if total == 0:
        parts.append(f"No camera events were recorded in the last {period_word}.")
    else:
        kind_parts = []
        for kind, count in sorted(by_kind.items(), key=lambda kv: -kv[1]):
            kind_parts.append(f"{count} {_kind_label(kind)}")
        parts.append(f"In the last {period_word}, {total} events were recorded: " + "; ".join(kind_parts) + ".")

        if by_device:
            top_device = max(by_device, key=by_device.get)
            parts.append(f"The most active camera was device #{top_device} with {by_device[top_device]} events.")

        if peak_hour is not None:
            parts.append(f"Activity peaked around {peak_hour}:00 with {peak_count} events in that hour.")

    narrative = " ".join(parts)

    with session_scope(settings) as db:
        # Replace any existing digest for the same owner/period/window.
        existing = (
            db.query(Digest)
            .filter_by(owner_id=owner_id, period=period)
            .filter(Digest.started_at == started_at)
            .first()
        )
        if existing is not None:
            existing.narrative = narrative
            existing.event_count = total
            existing.ended_at = ended_at
            existing.created_at = datetime.now(timezone.utc)
            db.commit()
            return existing

        digest = Digest(
            owner_id=owner_id,
            period=period,
            started_at=started_at,
            ended_at=ended_at,
            narrative=narrative,
            event_count=total,
        )
        db.add(digest)
        db.commit()
        db.refresh(digest)
        return digest


def latest_digest(
    owner_id: int,
    period: str = "daily",
    *,
    settings: Optional[Settings] = None,
) -> Optional[dict[str, Any]]:
    """Return the most recent digest for an owner/period."""
    settings = settings or get_settings()
    with session_scope(settings) as db:
        row = (
            db.query(Digest)
            .filter_by(owner_id=owner_id, period=period)
            .order_by(Digest.created_at.desc())
            .first()
        )
        if row is None:
            return None
        return {
            "id": row.id,
            "period": row.period,
            "started_at": row.started_at.isoformat(),
            "ended_at": row.ended_at.isoformat(),
            "narrative": row.narrative,
            "event_count": row.event_count,
            "created_at": row.created_at.isoformat(),
        }
