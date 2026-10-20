"""Device registry and camera event endpoints.

Every read and write is scoped to the authenticated owner.  Identifiers that
belong to somebody else result in ``404`` so that the API does not disclose
the existence of foreign objects (IDOR protection).
"""

from __future__ import annotations

import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..crypto import encrypt_bytes  # noqa: F401  (kept for API compatibility)
from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf, get_pagination
from ..models import CameraEvent, Device, DeviceNonce, DeviceStatus, DeviceType, User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import DEVICE_DELETE, DEVICE_READ, DEVICE_WRITE, EVENT_READ, EVENT_WRITE
from ..schemas import DeviceCreate, DeviceOut, DeviceUpdate, EventCreate, EventOut
from ..services import audit
from ..services.cameras import (
    CameraFetchError,
    UnsafeURLError,
    fetch_snapshot,
    generate_device_token,
    hash_device_token,
    verify_device_signature,
)
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])


def _device_out(device: Device, event_count: int = 0) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        name=device.name,
        device_type=device.device_type,
        status=device.status,
        location_label=device.location_label,
        has_stream_url=bool(device.stream_url),
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
        event_count=event_count,
    )


def _event_out(event: CameraEvent, device_name: str = "") -> EventOut:
    try:
        metadata = json.loads(event.metadata_json or "{}")
    except ValueError:  # pragma: no cover - defensive
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return EventOut(
        id=event.id,
        device_id=event.device_id,
        device_name=device_name,
        kind=event.kind,
        summary=event.summary,
        confidence=event.confidence,
        occurred_at=event.occurred_at,
        metadata=metadata,
    )


def _get_owned_device(db: Session, device_id: int, user: User) -> Device:
    device = db.get(Device, device_id)
    if device is None or device.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return device


@router.get("", response_model=list[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> list[DeviceOut]:
    """List the cameras of the authenticated owner."""
    counts = dict(
        db.execute(
            select(CameraEvent.device_id, func.count(CameraEvent.id))
            .join(Device, Device.id == CameraEvent.device_id)
            .where(Device.owner_id == user.id)
            .group_by(CameraEvent.device_id)
        ).all()
    )
    devices = db.scalars(
        select(Device).where(Device.owner_id == user.id).order_by(Device.id)
    ).all()
    return [_device_out(device, int(counts.get(device.id, 0))) for device in devices]


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(enforce_csrf)])
def create_device(
    payload: DeviceCreate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> DeviceOut:
    """Register a new camera for the authenticated owner."""
    if not _has_permission(user, DEVICE_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    settings = get_settings()
    if payload.device_type == DeviceType.IP_CAMERA and not payload.stream_url:
        raise HTTPException(
            status_code=422,
            detail="an IP camera requires a stream URL",
        )
    if payload.stream_url:
        from ..services.cameras import validate_camera_url

        try:
            validate_camera_url(payload.stream_url, settings)
        except UnsafeURLError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = db.scalar(
        select(Device).where(Device.owner_id == user.id, Device.name == payload.name)
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a device with this name already exists")

    device = Device(
        owner_id=user.id,
        name=payload.name,
        device_type=payload.device_type.value,
        location_label=payload.location_label,
        status=DeviceStatus.ACTIVE.value,
        stream_url=payload.stream_url,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    audit.record(
        db,
        action="device.create",
        actor_user_id=user.id,
        target_type="device",
        target_id=device.id,
        ip=_client_ip(request),
        detail={"device_type": device.device_type},
    )
    return _device_out(device)


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: int, db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> DeviceOut:
    """Return a single camera of the authenticated owner."""
    device = _get_owned_device(db, device_id, user)
    count = int(
        db.scalar(select(func.count(CameraEvent.id)).where(CameraEvent.device_id == device.id)) or 0
    )
    return _device_out(device, count)


@router.patch("/{device_id}", response_model=DeviceOut, dependencies=[Depends(enforce_csrf)])
def update_device(
    device_id: int,
    payload: DeviceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> DeviceOut:
    """Update a camera of the authenticated owner."""
    device = _get_owned_device(db, device_id, user)
    if not _has_permission(user, DEVICE_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    if payload.name is not None:
        clash = db.scalar(
            select(Device).where(
                Device.owner_id == user.id, Device.name == payload.name, Device.id != device.id
            )
        )
        if clash is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a device with this name already exists")
        device.name = payload.name
    if payload.location_label is not None:
        device.location_label = payload.location_label
    if payload.status is not None:
        device.status = payload.status.value
    if payload.stream_url is not None:
        from ..services.cameras import validate_camera_url

        try:
            validate_camera_url(payload.stream_url, get_settings())
        except UnsafeURLError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        device.stream_url = payload.stream_url

    db.commit()
    db.refresh(device)
    audit.record(
        db,
        action="device.update",
        actor_user_id=user.id,
        target_type="device",
        target_id=device.id,
        ip=_client_ip(request),
    )
    return _device_out(device)


@router.delete("/{device_id}", dependencies=[Depends(enforce_csrf)])
def delete_device(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Delete a camera and its events."""
    device = _get_owned_device(db, device_id, user)
    if not _has_permission(user, DEVICE_DELETE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    db.delete(device)
    db.commit()
    audit.record(
        db,
        action="device.delete",
        actor_user_id=user.id,
        target_type="device",
        target_id=device_id,
        ip=_client_ip(request),
    )
    return {"ok": True}


@router.post("/{device_id}/rotate-token", dependencies=[Depends(enforce_csrf)])
def rotate_device_token(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, str]:
    """Issue a fresh ingestion token for a device."""
    device = _get_owned_device(db, device_id, user)
    if not _has_permission(user, DEVICE_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    token = generate_device_token()
    device.device_token_hash = hash_device_token(token)
    db.commit()
    audit.record(
        db,
        action="device.rotate_token",
        actor_user_id=user.id,
        target_type="device",
        target_id=device.id,
        ip=_client_ip(request),
    )
    return {"device_token": token}


@router.get("/{device_id}/events", response_model=list[EventOut])
def list_events(
    device_id: int,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> list[EventOut]:
    """List the events of one of the owner's cameras."""
    if not _has_permission(user, EVENT_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    device = _get_owned_device(db, device_id, user)
    limit, offset = get_pagination(limit, offset)
    events = db.scalars(
        select(CameraEvent)
        .where(CameraEvent.device_id == device.id)
        .order_by(CameraEvent.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [_event_out(event, device.name) for event in events]


@router.post("/{device_id}/events", response_model=EventOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(enforce_csrf)])
def create_event(
    device_id: int,
    payload: EventCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> EventOut:
    """Record an event for one of the owner's cameras."""
    device = _get_owned_device(db, device_id, user)
    if not _has_permission(user, EVENT_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "event_write",
            f"user:{user.id}",
            settings.upload_rate_limit,
            settings.upload_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many events, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    event = CameraEvent(
        device_id=device.id,
        owner_id=user.id,
        kind=payload.kind,
        summary=payload.summary[:400],
        confidence=payload.confidence,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        metadata_json=json.dumps(payload.metadata)[:4000],
    )
    db.add(event)
    device.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    audit.record(
        db,
        action="event.create",
        actor_user_id=user.id,
        target_type="camera_event",
        target_id=event.id,
        ip=_client_ip(request),
        detail={"device_id": device.id, "kind": event.kind},
    )
    return _event_out(event, device.name)


@router.post("/{device_id}/snapshot", dependencies=[Depends(enforce_csrf)])
def device_snapshot(
    device_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> Response:
    """Fetch a single snapshot from an IP camera.

    The URL is validated against the SSRF rules before any connection is
    opened and the response is capped in size and time.
    """
    device = _get_owned_device(db, device_id, user)
    if not _has_permission(user, DEVICE_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    if not device.stream_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="this device has no stream URL")

    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "camera_snapshot",
            f"user:{user.id}",
            settings.upload_rate_limit,
            settings.upload_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many snapshot requests",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    try:
        snapshot = fetch_snapshot(device.stream_url, settings)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CameraFetchError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    audit.record(
        db,
        action="device.snapshot",
        actor_user_id=user.id,
        target_type="device",
        target_id=device.id,
        ip=_client_ip(request),
    )
    return Response(
        content=snapshot.content,
        media_type=snapshot.content_type,
        headers={"Cache-Control": "no-store, max-age=0", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/ingest", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def ingest_event(
    request: Request,
    db: Session = Depends(get_db),
) -> EventOut:
    """Accept an event pushed by a device (phone, wearable, IP camera).

    The request is authenticated with the device token and an HMAC signature
    over the timestamp, nonce and body, which prevents spoofing and replay.
    """
    settings = get_settings()
    device_id = request.headers.get("x-device-id")
    timestamp = request.headers.get("x-device-timestamp", "")
    nonce = request.headers.get("x-device-nonce", "")
    signature = request.headers.get("x-device-signature", "")
    device_secret = request.headers.get("x-device-token", "")

    if not device_id or not timestamp or not nonce or not signature or not device_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device authentication required")

    try:
        device_pk = int(device_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device authentication required") from exc

    device = db.get(Device, device_pk)
    if device is None or not device.device_token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device authentication required")

    # The plaintext token is never stored - only its hash - but the token
    # itself is the shared secret for the HMAC signature.
    if not hmac.compare_digest(hash_device_token(device_secret), device.device_token_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="device authentication required")

    body = await request.body()
    if not verify_device_signature(
        device_secret,
        timestamp,
        nonce,
        body,
        signature,
        max_age=settings.device_token_ttl_seconds,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid device signature")

    # Replay protection: the nonce may only be used once.
    db.add(DeviceNonce(device_id=device.id, nonce=nonce))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate request") from exc

    try:
        payload = _parse_ingest_body(body)
    except HTTPException as exc:
        raise exc from None
    event = CameraEvent(
        device_id=device.id,
        owner_id=device.owner_id,
        kind=payload.get("kind", "motion")[:48],
        summary=str(payload.get("summary", ""))[:400],
        confidence=float(min(max(float(payload.get("confidence", 0.0)), 0.0), 1.0)),
        occurred_at=datetime.now(timezone.utc),
        metadata_json=json.dumps(payload.get("metadata") or {})[:4000],
    )
    db.add(event)
    device.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return _event_out(event, device.name)


def _parse_ingest_body(body: bytes) -> dict[str, Any]:
    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid payload") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid payload")
    return data


def _has_permission(user: User, permission: str) -> bool:
    from ..rbac import has_permission as _check

    return _check(user.role, permission)


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
