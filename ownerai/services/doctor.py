"""Startup health probes + benchmark commands (Phase 3B rank #6).

Honest health checks: camera, model/provider, DB, disk.  Never fakes a
result - ``.unknown(reason:)`` is the honest answer when a dependency
can't be verified.  Ships behind the ``DOCTOR`` feature flag.
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import text

from ..db import get_engine, session_scope
from ..features import is_enabled
from ..models import Device
from ..services.ai import build_provider
from ..services.health import run_health_check
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class DoctorError(RuntimeError):
    """Raised when the doctor cannot run."""


@dataclass
class Probe:
    """A single health probe result."""

    name: str
    status: str  # ok | soft | loud | critical | unknown
    message: str
    detail: dict[str, Any] = field(default_factory=dict)
    latency_ms: Optional[float] = None


@dataclass
class DoctorReport:
    """Aggregated doctor report."""

    checks: list[Probe]
    overall: str  # ok | degraded | critical
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "timestamp": self.timestamp,
            "checks": [
                {
                    "name": p.name,
                    "status": p.status,
                    "message": p.message,
                    "detail": p.detail,
                    "latency_ms": p.latency_ms,
                }
                for p in self.checks
            ],
        }


def _severity_rank(status: str) -> int:
    return {"ok": 0, "unknown": 1, "soft": 2, "loud": 3, "critical": 4}.get(status, 5)


def probe_database() -> Probe:
    """Probe the database connection."""
    start = time.time()
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        return Probe("database", "ok", "database reachable", {"latency_ms": round(latency, 1)}, latency)
    except Exception as exc:  # pragma: no cover - infrastructure
        latency = (time.time() - start) * 1000
        return Probe(
            "database",
            "critical",
            f"database unreachable: {type(exc).__name__}",
            {"latency_ms": round(latency, 1)},
            latency,
        )


def probe_disk(settings: Settings) -> Probe:
    """Probe disk usage on the working directory."""
    start = time.time()
    try:
        usage = shutil.disk_usage(".")
        percent = (usage.used / usage.total) * 100 if usage.total else 0
        latency = (time.time() - start) * 1000
        if percent >= settings.doctor_disk_warn_percent:
            return Probe(
                "disk",
                "loud",
                f"disk usage at {percent:.0f}% (warn threshold {settings.doctor_disk_warn_percent}%)",
                {"usage_percent": round(percent, 1), "latency_ms": round(latency, 1)},
                latency,
            )
        return Probe(
            "disk",
            "ok",
            f"disk usage at {percent:.0f}%",
            {"usage_percent": round(percent, 1), "latency_ms": round(latency, 1)},
            latency,
        )
    except Exception as exc:  # pragma: no cover - infrastructure
        latency = (time.time() - start) * 1000
        return Probe(
            "disk",
            "unknown",
            f"could not read disk usage: {type(exc).__name__}",
            {"latency_ms": round(latency, 1)},
            latency,
        )


def probe_model(settings: Settings) -> Probe:
    """Probe the AI provider availability."""
    start = time.time()
    try:
        provider = build_provider(settings)
        latency = (time.time() - start) * 1000
        return Probe(
            "model",
            "ok",
            f"provider '{provider.name}' available",
            {"provider": provider.name, "latency_ms": round(latency, 1)},
            latency,
        )
    except Exception as exc:  # pragma: no cover - infrastructure
        latency = (time.time() - start) * 1000
        return Probe(
            "model",
            "unknown",
            f"provider unavailable: {type(exc).__name__}",
            {"latency_ms": round(latency, 1)},
            latency,
        )


def probe_cameras(settings: Settings) -> Probe:
    """Probe registered cameras for health."""
    start = time.time()
    try:
        with session_scope(settings) as db:
            cameras = db.query(Device).all()
        if not cameras:
            return Probe("cameras", "ok", "no cameras registered", {"count": 0})
        unhealthy = 0
        for cam in cameras:
            try:
                report = run_health_check(cam, settings=settings)
                if report.status != "healthy":
                    unhealthy += 1
            except Exception:
                unhealthy += 1
        latency = (time.time() - start) * 1000
        if unhealthy == 0:
            return Probe(
                "cameras",
                "ok",
                f"all {len(cameras)} camera(s) healthy",
                {"count": len(cameras), "latency_ms": round(latency, 1)},
                latency,
            )
        return Probe(
            "cameras",
            "loud",
            f"{unhealthy} of {len(cameras)} camera(s) degraded",
            {"count": len(cameras), "unhealthy": unhealthy, "latency_ms": round(latency, 1)},
            latency,
        )
    except Exception as exc:  # pragma: no cover - infrastructure
        latency = (time.time() - start) * 1000
        return Probe(
            "cameras",
            "unknown",
            f"could not probe cameras: {type(exc).__name__}",
            {"latency_ms": round(latency, 1)},
            latency,
        )


def run_doctor(settings: Optional[Settings] = None) -> DoctorReport:
    """Run all health probes and return an aggregated report."""
    if not is_enabled("DOCTOR"):
        raise DoctorError("DOCTOR feature is not enabled")
    settings = settings or get_settings()
    checks: list[Probe] = [
        probe_database(),
        probe_disk(settings),
        probe_model(settings),
        probe_cameras(settings),
    ]
    worst = max((_severity_rank(c.status) for c in checks), default=0)
    if worst >= 4:
        overall = "critical"
    elif worst >= 3:
        overall = "degraded"
    elif worst >= 2:
        overall = "degraded"
    else:
        overall = "ok"
    return DoctorReport(
        checks=checks,
        overall=overall,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def benchmark_provider(
    runs: int = 10,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Benchmark the AI provider with ``runs`` completion calls."""
    if not is_enabled("DOCTOR"):
        raise DoctorError("DOCTOR feature is not enabled")
    settings = settings or get_settings()
    runs = max(1, min(runs, 50))
    provider = build_provider(settings)
    latencies: list[float] = []
    errors = 0
    for _ in range(runs):
        start = time.time()
        try:
            provider.complete([{"role": "user", "content": "ping"}], max_tokens=5)
            latencies.append((time.time() - start) * 1000)
        except Exception:
            errors += 1
    if latencies:
        latencies.sort()
        return {
            "provider": provider.name,
            "runs": runs,
            "errors": errors,
            "latency_ms": {
                "min": round(min(latencies), 1),
                "max": round(max(latencies), 1),
                "mean": round(sum(latencies) / len(latencies), 1),
                "median": round(latencies[len(latencies) // 2], 1),
            },
        }
    return {"provider": provider.name, "runs": runs, "errors": errors, "latency_ms": None}
