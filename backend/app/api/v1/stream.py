"""Live streaming router: MJPEG video feed, snapshot retrieval, and WebSocket broadcasts."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Generator, Optional

import cv2
from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import decode_access_token
from ...models.entities import Camera, User
from ...workers.inference_worker import worker_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stream", tags=["stream"])


def get_stream_user_optional(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Enforce authentication for media streams, snapshots, and binary endpoints."""
    raw_token = None
    if authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    elif token:
        raw_token = token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required for media stream",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired stream authorization token",
        )

    user = db.get(User, payload["sub"])
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found",
        )
    return user


def _generate_mjpeg_frames(camera_id: str) -> Generator[bytes, None, None]:
    worker = worker_registry.get_or_start_worker(camera_id)
    target_interval = 1.0 / 30.0  # 33.3ms for smooth 30 FPS stream

    while True:
        t0 = time.time()
        frame = worker.latest_annotated_frame
        if frame is None:
            time.sleep(0.03)
            continue

        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            time.sleep(0.01)
            continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )
        elapsed = time.time() - t0
        time.sleep(max(0.005, target_interval - elapsed))


@router.get("/mjpeg/{camera_id}")
def stream_mjpeg(
    camera_id: str,
    user: User = Depends(get_stream_user_optional),
    db: Session = Depends(get_db),
):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    return StreamingResponse(
        _generate_mjpeg_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/snapshot/{filename}")
def get_snapshot(
    filename: str,
    user: User = Depends(get_stream_user_optional),
):
    settings = get_settings()
    # Strict path traversal protection
    safe_name = os.path.basename(filename)
    base_dir = settings.snapshot_storage_path.resolve()
    filepath = (base_dir / safe_name).resolve()
    if not filepath.is_relative_to(base_dir) or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(str(filepath), media_type="image/jpeg")


@router.websocket("/ws")
async def websocket_events(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket for real-time live event broadcasts with token authentication."""
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        while True:
            # Send periodic heartbeats & active track updates
            active_info = []
            for cid, w in list(worker_registry.workers.items()):
                tracks_summary = [
                    {
                        "track_id": t.track_id,
                        "verified_name": t.verified_name,
                        "bbox": t.bbox,
                    }
                    for t in w.latest_tracks
                ]
                active_info.append({"camera_id": cid, "tracks": tracks_summary})

            await websocket.send_json({"type": "live_heartbeat", "cameras": active_info, "timestamp": time.time()})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WebSocket event loop closed: %s", exc)
