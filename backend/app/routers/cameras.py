"""Camera registry, ingestion, events, snapshots, notifications."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from sqlalchemy import select

from ..config import Settings
from ..dependencies import DbDep, require_csrf, require_owner, require_user
from ..models.cameras import CameraEvent, Notification
from ..models.session import Session as SessionRow
from ..models.user import User
from ..schemas import CameraIn, CameraOut, CameraUpdateIn
from ..services import audit_service, camera_service
from ..services.camera_service import CameraError
from ..vision.pipeline import FrameProcessor

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _managers(request):  # type: ignore[no-untyped-def]
    from ..workers.cameras import manager
    return manager


def _out(camera, managers) -> CameraOut:  # type: ignore[no-untyped-def]
    return CameraOut(
        id=camera.id, name=camera.name, kind=camera.kind,
        source=camera.source, enabled=camera.enabled,
        retention_days=camera.retention_days,
        running=managers.is_running(camera.id))


@router.post("", status_code=201)  # no response_model: returns the one-time token
async def create(
    body: CameraIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    user, _row = pair
    camera, raw_token = await camera_service.create_camera(
        db, request.app.state.settings,
        name=body.name, kind=body.kind, source=body.source)
    await audit_service.record(
        db, "camera.create", actor_user_id=user.id,
        target=f"#{camera.id}:{camera.kind}")
    await db.commit()
    out = _out(camera, _managers(request))
    # the one and only place the raw ingest token is ever shown
    return {**out.model_dump(), "token": raw_token,
            "health": camera_service.effective_status(None)}


@router.get("", response_model=list[CameraOut])
async def listing(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
) -> list[CameraOut]:
    managers = _managers(request)
    out = []
    for camera in await camera_service.list_cameras(db):
        item = _out(camera, managers)
        health = await camera_service.health_row(db, camera.id)
        item.health = camera_service.effective_status(health)
        out.append(item)
    await db.commit()
    return out


@router.patch("/{camera_id}", response_model=CameraOut)
async def update(
    camera_id: int,
    body: CameraUpdateIn,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    request: Request,
    db: DbDep,
) -> CameraOut:
    camera = await camera_service.update_camera(
        db, camera_id, enabled=body.enabled, name=body.name,
        retention_days=body.retention_days)
    if body.enabled is False:
        _managers(request).stop(camera_id)
    await audit_service.record(db, "camera.update", target=f"#{camera_id}")
    await db.commit()
    item = _out(camera, _managers(request))
    health = await camera_service.health_row(db, camera_id)
    item.health = camera_service.effective_status(health)
    return item


@router.post("/{camera_id}/start")
async def start(
    camera_id: int,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    camera = await camera_service.get_camera(db, camera_id)
    if camera is None:
        raise CameraError("not_found", "camera not found", 404)
    started = _managers(request).start(
        camera, None, request.app.state.settings)
    await audit_service.record(db, "camera.start", target=f"#{camera_id}")
    await db.commit()
    return {"ok": True,
            "running": _managers(request).is_running(camera_id),
            "already": not started}


@router.post("/{camera_id}/stop")
async def stop(
    camera_id: int,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    was_running = _managers(request).stop(camera_id)
    await audit_service.record(db, "camera.stop", target=f"#{camera_id}")
    await db.commit()
    return {"ok": True, "was_running": was_running}


# ------------------------------------------------------------ HMAC ingest
@router.post("/{camera_id}/frame")
async def ingest_frame(
    camera_id: int,
    request: Request,
    db: DbDep,
    token: str = Header(default="", alias="X-Camera-Token"),
    ts: str = Header(default="", alias="X-Timestamp"),
    nonce: str = Header(default="", alias="X-Nonce"),
    signature: str = Header(default="", alias="X-Signature"),
) -> dict:
    """Phone/PWA frames: token + HMAC + nonce, processed then discarded."""
    body = (await request.body())[:camera_service.MAX_FRAME_BYTES + 1]
    settings: Settings = request.app.state.settings
    await camera_service.verify_ingest(
        db, camera_id=camera_id, raw_token=token, ts=ts, nonce=nonce,
        signature=signature, body=body)

    import cv2
    import numpy as np

    frame = cv2.imdecode(np.frombuffer(body, dtype=np.uint8),
                         cv2.IMREAD_COLOR)
    if frame is None:
        raise CameraError("bad_image", "frame is not a decodable image", 422)

    processor = FrameProcessor()
    verdict = processor.process(frame, now=0.0)
    if verdict.persons > 0:
        event = processor.make_event(frame, verdict, now=0.0)
        await camera_service.record_event(
            db, settings, camera_id=camera_id, kind="person",
            person_count=event.person_count,
            motion_score=event.motion_score,
            snapshot_jpeg=event.snapshot_jpeg,
            snapshot_status=event.snapshot_status)
    await camera_service.mark_frame(db, camera_id, fps=1.0)
    await db.commit()
    return {"motion_score": verdict.motion_score,
            "persons": verdict.persons}


# ---------------------------------------------------------- events/snapshots
@router.get("/{camera_id}/events")
async def events(
    camera_id: int,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    db: DbDep,
    limit: int = 50,
) -> dict:
    rows = (await db.execute(
        select(CameraEvent)
        .where(CameraEvent.camera_id == camera_id)
        .order_by(CameraEvent.ts.desc()).limit(min(max(limit, 1), 200))
    )).scalars().all()
    await db.commit()
    return {"items": [
        {"id": r.id, "ts": r.ts.isoformat(), "kind": r.kind,
         "person_count": r.person_count, "motion_score": r.motion_score,
         "snapshot_status": r.snapshot_status,
         "has_snapshot": bool(r.snapshot_encrypted)}
        for r in rows], "count": len(rows)}


@router.get("/{camera_id}/events/{event_id}/snapshot")
async def snapshot(
    camera_id: int,
    event_id: int,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
):
    event = await db.get(CameraEvent, event_id)
    settings: Settings = request.app.state.settings
    if event is None or event.camera_id != camera_id or not event.snapshot_encrypted:
        raise CameraError("not_found", "snapshot not found", 404)
    image = await camera_service.decrypt_snapshot(settings,
                                                  event.snapshot_encrypted)
    await db.commit()
    return Response(
        image, media_type="image/jpeg",
        headers={"cache-control": "no-store",
                 "content-disposition": f'inline; filename="event-{event_id}.jpg"'})


@router.post("/purge")
async def purge(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    db: DbDep,
) -> dict:
    removed = await camera_service.purge_expired(db)
    await audit_service.record(db, "camera.purge",
                               detail={"removed": removed})
    await db.commit()
    return {"removed": removed}


# --------------------------------------------------------------- notifs
notifications_router = APIRouter(prefix="/api/notifications",
                                 tags=["notifications"])


@notifications_router.get("")
async def notifications_list(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    db: DbDep,
) -> dict:
    rows = (await db.execute(
        select(Notification).order_by(Notification.ts.desc()).limit(50)
    )).scalars().all()
    await db.commit()
    return {"items": [
        {"id": r.id, "ts": r.ts.isoformat(), "kind": r.kind,
         "title": r.title, "body": r.body, "is_read": r.is_read}
        for r in rows],
        "unread": sum(1 for r in rows if not r.is_read)}


@notifications_router.post("/{notif_id}/read")
async def notifications_read(
    notif_id: int,
    _pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
) -> dict:
    row = await db.get(Notification, notif_id)
    if row is None:
        raise CameraError("not_found", "notification not found", 404)
    row.is_read = True
    await db.commit()
    return {"ok": True}
