"""Camera registry + ingest + events + retention service.

Rules enforced here:
- RTSP sources go through the SSRF validator (Phase 2) — private hosts
  blocked unless OWNERAI_ALLOW_PRIVATE_CAMERA_HOSTS=true
- ingest tokens are single-use knowledge: stored as SHA-256 hash only
- frames are authenticated by HMAC-SHA256 with replay protection
- snapshots only ever stored encrypted (AES-256-GCM); when faces cannot
  be blurred the event keeps metadata only ("withheld")
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.cameras import (
    Camera,
    CameraEvent,
    CameraHealth,
    IngestNonce,
    Notification,
)
from ..models.user import utcnow
from ..security import ssrf
from ..security.crypto import decrypt_text, encrypt_text
from .memory_service import memory_key


class CameraError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


# ------------------------------------------------------------------- tokens
def _token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_signature(raw_token: str, camera_id: int, ts: str, nonce: str,
                      body: bytes) -> str:
    return hmac.new(
        raw_token.encode("utf-8"),
        f"{camera_id}.{ts}.{nonce}.{hashlib.sha256(body).hexdigest()}".encode(),
        hashlib.sha256).hexdigest()


# ---------------------------------------------------------------- registry
async def create_camera(session: AsyncSession, settings: Settings, *,
                        name: str, kind: str, source: str) -> tuple[Camera, str]:
    name = " ".join(name.split())[:120]
    if not name:
        raise CameraError("empty_name", "camera name cannot be empty", 422)
    if kind not in ("webcam", "phone", "rtsp"):
        raise CameraError("bad_kind", "kind must be webcam, phone or rtsp", 422)
    source = source.strip()[:500]
    if kind == "rtsp":
        try:
            ssrf.validate_url(source,
                              allow_private=settings.allow_private_camera_hosts)
        except ssrf.SSRFError as exc:
            raise CameraError("ssrf_blocked", str(exc), 403) from exc
    raw_token = secrets.token_urlsafe(32)
    camera = Camera(name=name, kind=kind, source=source,
                    token_hash=_token_hash(raw_token))
    session.add(camera)
    await session.flush()
    session.add(CameraHealth(camera_id=camera.id, status="starting"))
    await session.flush()
    return camera, raw_token


async def get_camera(session: AsyncSession, camera_id: int) -> Camera | None:
    return await session.get(Camera, camera_id)


async def list_cameras(session: AsyncSession) -> list[Camera]:
    return list((await session.execute(
        select(Camera).order_by(Camera.id.asc()))).scalars().all())


async def update_camera(session: AsyncSession, camera_id: int, *,
                        enabled: bool | None = None, name: str | None = None,
                        retention_days: int | None = None) -> Camera:
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise CameraError("not_found", "camera not found", 404)
    if enabled is not None:
        camera.enabled = enabled
    if name is not None:
        cleaned = " ".join(name.split())[:120]
        if not cleaned:
            raise CameraError("empty_name", "camera name cannot be empty", 422)
        camera.name = cleaned
    if retention_days is not None:
        if not 1 <= retention_days <= 90:
            raise CameraError("bad_retention",
                              "retention must be 1..90 days", 422)
        camera.retention_days = retention_days
    await session.flush()
    return camera


# ------------------------------------------------------------------ events
async def record_event(session: AsyncSession, settings: Settings, *,
                       camera_id: int, kind: str, person_count: int,
                       motion_score: float, snapshot_jpeg: bytes | None,
                       snapshot_status: str) -> CameraEvent:
    event = CameraEvent(
        camera_id=camera_id, kind=kind, person_count=person_count,
        motion_score=motion_score,
        snapshot_encrypted=(encrypt_text(memory_key(settings), snapshot_jpeg.decode("latin-1"))
                            if snapshot_jpeg else None),
        snapshot_status=snapshot_status)
    session.add(event)
    await session.flush()
    health = await session.get(CameraHealth, camera_id)
    if health is not None:
        health.last_event_at = utcnow()
        health.updated_at = utcnow()
    if kind == "person":
        session.add(Notification(
            camera_id=camera_id, kind="person",
            title=f"Person seen on {camera_id}",
            body=f"{person_count} person(s) detected (motion "
                 f"{motion_score:.1%}); snapshot {snapshot_status}"))
    return event


# ------------------------------------------------------------------ ingest
MAX_FRAME_BYTES = 500_000
TS_SKEW_S = 300  # +-5 minutes


def _parse_ts(ts: str) -> datetime:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CameraError("bad_timestamp", "timestamp not ISO-8601", 401) from exc
    if dt.tzinfo is None:  # treat naive as UTC
        dt = dt.replace(tzinfo=UTC)
    return dt


async def verify_ingest(session: AsyncSession, *, camera_id: int,
                        raw_token: str, ts: str, nonce: str, signature: str,
                        body: bytes) -> Camera:
    if len(body) > MAX_FRAME_BYTES:
        raise CameraError("payload_too_large", "frame too large", 413)
    camera = await session.get(Camera, camera_id)
    if camera is None:
        raise CameraError("not_found", "camera not found", 404)
    if not camera.enabled:
        raise CameraError("camera_disabled", "camera is disabled", 403)
    if not hmac.compare_digest(_token_hash(raw_token), camera.token_hash):
        raise CameraError("bad_token", "invalid camera token", 401)
    when = _parse_ts(ts)
    now = datetime.now(UTC)
    if abs((now - when).total_seconds()) > TS_SKEW_S:
        raise CameraError("stale_timestamp", "frame timestamp is too old", 401)
    if hmac.compare_digest(
            compute_signature(raw_token, camera_id, ts, nonce, body), signature):
        pass
    else:
        raise CameraError("bad_signature", "frame signature invalid", 401)
    # replay protection: a nonce is accepted at most once
    seen = await session.get(IngestNonce, nonce)
    if seen is not None:
        raise CameraError("replay", "this frame was already ingested", 409)
    session.add(IngestNonce(nonce=nonce, camera_id=camera_id))
    await session.flush()
    return camera


# ---------------------------------------------------------------- retention
async def purge_expired(session: AsyncSession) -> dict:
    """Delete events and old nonces past retention. Returns real counts."""
    now = utcnow()
    removed = {"events": 0, "notifications": 0, "nonces": 0}
    cameras = await list_cameras(session)
    for camera in cameras:
        cutoff = now - timedelta(days=camera.retention_days)
        result = await session.execute(
            delete(CameraEvent).where(
                CameraEvent.camera_id == camera.id,
                CameraEvent.ts < cutoff))
        removed["events"] += int(getattr(result, "rowcount", 0) or 0)
    stale = now - timedelta(days=30)
    result = await session.execute(
        delete(Notification).where(Notification.ts < stale))
    removed["notifications"] = int(getattr(result, "rowcount", 0) or 0)
    result = await session.execute(
        delete(IngestNonce).where(IngestNonce.ts < now - timedelta(hours=1)))
    removed["nonces"] = int(getattr(result, "rowcount", 0) or 0)
    await session.flush()
    return removed


# ------------------------------------------------------------------- health
async def health_row(session: AsyncSession, camera_id: int) -> CameraHealth | None:
    return await session.get(CameraHealth, camera_id)


async def mark_frame(session: AsyncSession, camera_id: int, *, fps: float) -> None:
    health = await session.get(CameraHealth, camera_id)
    if health is None:
        return
    health.status = "online"
    health.last_frame_at = utcnow()
    health.frames += 1
    health.fps = fps
    health.error = None
    health.updated_at = utcnow()


def effective_status(health: CameraHealth | None, *, stale_after_s: int = 30) -> dict:
    """Honest status: a live task with a dead camera reports offline."""
    if health is None:
        return {"status": "unknown"}
    if health.status == "online" and health.last_frame_at is not None:
        age = (utcnow() - health.last_frame_at).total_seconds()
        if age > stale_after_s:
            return {"status": "offline", "reason": "no frames recently",
                    "age_seconds": round(age)}
    return {"status": health.status,
            "error": health.error,
            "last_frame_at": (health.last_frame_at.isoformat()
                              if health.last_frame_at else None),
            "fps": health.fps,
            "frames": health.frames}


# ---------------------------------------------------------------- snapshots
async def decrypt_snapshot(settings: Settings, encrypted: str) -> bytes:
    text = decrypt_text(memory_key(settings), encrypted)
    return text.encode("latin-1")
