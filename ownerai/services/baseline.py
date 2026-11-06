"""Learned 'normal' activity baseline (Phase 3 item #2, Phase 3B rank #2).

Per camera and time-of-day (hour-of-week bucket), learn routine activity from
stored CameraEvent metadata and alert on genuine deviations, with an
explanation of why.

Only stored event metadata is used - never raw frames, never stranger
identification.  Ships behind the ``LEARNED_BASELINE`` feature flag.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from ..db import session_scope
from ..features import is_enabled
from ..models import ActivityBaseline, CameraEvent, Device
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class BaselineError(RuntimeError):
    """Raised when baseline learning/evaluation cannot run."""


@dataclass
class Deviation:
    """A detected deviation from the learned baseline."""

    device_id: int
    hour_of_week: int
    observed: int
    mean: float
    stddev: float
    z_score: float
    explanation: str


def _hour_of_week(when: datetime) -> int:
    """0..167 bucket: hour of day + weekday * 24."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.weekday() * 24 + when.hour


def learn_baselines(
    owner_id: int,
    *,
    days: int | None = None,
    settings: Optional[Settings] = None,
) -> int:
    """Learn activity baselines from the last ``days`` of events.

    Returns the number of baseline rows upserted.  Idempotent.
    """
    if not is_enabled("LEARNED_BASELINE"):
        raise BaselineError("LEARNED_BASELINE feature is not enabled")
    settings = settings or get_settings()
    window = days or settings.baseline_learn_window_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=window)

    with session_scope(settings) as db:
        # Fetch all events in the window, then bucket in Python (SQLite
        # strftime on tz-aware datetimes is unreliable across drivers).
        rows = (
            db.execute(
                select(CameraEvent.device_id, CameraEvent.occurred_at)
                .where(CameraEvent.owner_id == owner_id)
                .where(CameraEvent.occurred_at >= cutoff)
            )
            .all()
        )

        buckets: dict[tuple[int, int], list[int]] = {}
        for device_id, occurred_at in rows:
            try:
                h = _hour_of_week(occurred_at)
            except (TypeError, ValueError):
                continue
            buckets.setdefault((device_id, h), []).append(1)

        upserted = 0
        now = datetime.now(timezone.utc)
        for (device_id, h), counts in buckets.items():
            n = len(counts)
            mean = sum(counts) / n
            variance = sum((c - mean) ** 2 for c in counts) / n
            stddev = variance ** 0.5

            row = (
                db.query(ActivityBaseline)
                .filter_by(device_id=device_id, hour_of_week=h)
                .first()
            )
            if row is None:
                row = ActivityBaseline(
                    device_id=device_id,
                    owner_id=owner_id,
                    hour_of_week=h,
                )
                db.add(row)
            row.mean_events = round(mean, 4)
            row.stddev_events = round(stddev, 4)
            row.sample_count = n
            row.last_learned_at = now
            upserted += 1

        db.commit()
        return upserted


def evaluate_deviation(
    device_id: int,
    observed_count: int,
    when: datetime,
    *,
    settings: Optional[Settings] = None,
) -> Optional[Deviation]:
    """Compare an observed event count against the learned baseline.

    Returns a :class:`Deviation` when the observation is a genuine outlier
    (beyond ``baseline_deviation_multiplier`` std-devs), else ``None``.
    """
    if not is_enabled("LEARNED_BASELINE"):
        return None
    settings = settings or get_settings()

    h = _hour_of_week(when)
    with session_scope(settings) as db:
        row = (
            db.query(ActivityBaseline)
            .filter_by(device_id=device_id, hour_of_week=h)
            .first()
        )
    if row is None or row.sample_count < 3:
        # Not enough data to establish a baseline.
        return None

    stddev = row.stddev_events
    if stddev == 0:
        # Baseline is perfectly flat; any non-zero observation is a deviation.
        if observed_count != int(row.mean_events):
            return Deviation(
                device_id=device_id,
                hour_of_week=h,
                observed=observed_count,
                mean=row.mean_events,
                stddev=0.0,
                z_score=float("inf"),
                explanation=(
                    f"baseline is flat at {row.mean_events:.1f} events but "
                    f"{observed_count} observed"
                ),
            )
        return None

    z_score = abs(observed_count - row.mean_events) / stddev
    if z_score < settings.baseline_deviation_multiplier:
        return None

    direction = "above" if observed_count > row.mean_events else "below"
    return Deviation(
        device_id=device_id,
        hour_of_week=h,
        observed=observed_count,
        mean=row.mean_events,
        stddev=round(stddev, 4),
        z_score=round(z_score, 2),
        explanation=(
            f"{observed_count} events at this hour-of-week versus a learned "
            f"baseline of {row.mean_events:.1f} ± {stddev:.1f} "
            f"({direction} by {z_score:.1f} std-devs)"
        ),
    )


def latest_baseline(device_id: int, *, settings: Optional[Settings] = None) -> Optional[dict[str, Any]]:
    """Return the baseline row for a device's current hour-of-week bucket."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    h = _hour_of_week(now)
    with session_scope(settings) as db:
        row = (
            db.query(ActivityBaseline)
            .filter_by(device_id=device_id, hour_of_week=h)
            .first()
        )
        if row is None:
            return None
        return {
            "device_id": row.device_id,
            "hour_of_week": row.hour_of_week,
            "mean_events": row.mean_events,
            "stddev_events": row.stddev_events,
            "sample_count": row.sample_count,
            "last_learned_at": row.last_learned_at.isoformat(),
        }


def baseline_status_for_device(
    device: Device, *, settings: Optional[Settings] = None
) -> dict[str, Any]:
    """Summarise baseline state for one device (used by health/diagnostics)."""
    settings = settings or get_settings()
    info = latest_baseline(device.id, settings=settings)
    return {
        "device_id": device.id,
        "baseline_learned": info is not None,
        "current_hour_of_week_bucket": _hour_of_week(datetime.now(timezone.utc)),
        **(info or {}),
    }
