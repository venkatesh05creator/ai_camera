"""Cameras management router."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.entities import Camera, User
from ...schemas.schemas import CameraOut, CameraRegister, CameraUpdate
from ...services.audit_service import log_action
from ...services.camera_service import camera_manager, ensure_default_webcam
from ...workers.inference_worker import worker_registry
from .auth import get_current_user

from ...core.security import PERM_CAMERAS_WRITE, has_permission, validate_stream_url

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/health")
def get_all_cameras_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return live health telemetry (FPS, resolution, connection status, stale flag) for all cameras."""
    cameras = db.scalars(select(Camera)).all()
    health_list = []
    for c in cameras:
        h = camera_manager.get_camera_health(c.id)
        h["name"] = c.name
        h["source_type"] = c.source_type
        health_list.append(h)
    return health_list


@router.get("/{camera_id}/health")
def get_camera_health(camera_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return health telemetry for a specific camera."""
    cam = db.get(Camera, camera_id)
    if not cam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    h = camera_manager.get_camera_health(camera_id)
    h["name"] = cam.name
    h["source_type"] = cam.source_type
    return h


@router.get("", response_model=List[CameraOut])
def list_cameras(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Auto-seed default laptop camera if empty
    ensure_default_webcam(db, current_user.id)

    cameras = db.scalars(select(Camera).order_by(Camera.created_at)).all()
    return [CameraOut.model_validate(c) for c in cameras]



@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def register_camera(payload: CameraRegister, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_permission(current_user.role, PERM_CAMERAS_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    # SSRF & Stream URL format validation
    is_valid, validation_msg = validate_stream_url(payload.stream_url, source_type=payload.source_type)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation_msg)

    camera = Camera(
        name=payload.name,
        source_type=payload.source_type,
        location_label=payload.location_label,
        stream_url=payload.stream_url or "0",
        owner_user_id=current_user.id,
        status="online",
    )
    if payload.connection_secret:
        camera.set_secret(payload.connection_secret)


    db.add(camera)
    db.commit()
    db.refresh(camera)

    log_action(db, action="camera.register", resource_type="camera", actor_user_id=current_user.id, resource_id=camera.id, details={"name": camera.name})
    return camera


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    return camera


@router.put("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if payload.name is not None:
        camera.name = payload.name
    if payload.location_label is not None:
        camera.location_label = payload.location_label
    if payload.status is not None:
        camera.status = payload.status
    if payload.stream_url is not None:
        is_valid, validation_msg = validate_stream_url(payload.stream_url, source_type=camera.source_type)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=validation_msg)
        camera.stream_url = payload.stream_url

    if payload.stream_url is not None or (payload.status is not None and payload.status != "online"):
        worker_registry.stop_worker(camera_id)
        camera_manager.release_camera(camera_id)

    db.commit()
    db.refresh(camera)
    log_action(db, action="camera.update", resource_type="camera", actor_user_id=current_user.id, resource_id=camera.id)
    return camera


@router.post("/test-connection")
def test_stream_connection(
    payload: CameraRegister,
    current_user: User = Depends(get_current_user),
):
    """Test camera stream connectivity without persisting."""
    is_valid, validation_msg = validate_stream_url(payload.stream_url, source_type=payload.source_type)
    if not is_valid:
        return {"accessible": False, "error": validation_msg}

    # Verify if source can be accessed
    source = payload.stream_url or "0"
    if payload.source_type == "webcam":
        try:
            source = int(source) if str(source).isdigit() else 0
        except ValueError:
            source = 0

    import cv2
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        return {"accessible": False, "error": "Unable to connect or open video source"}
    
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return {"accessible": False, "error": "Connection opened, but failed to retrieve frame"}

    h, w = frame.shape[:2]
    return {
        "accessible": True,
        "resolution": f"{w}x{h}",
        "message": "Camera stream connected successfully",
    }



@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    worker_registry.stop_worker(camera_id)
    camera_manager.release_camera(camera_id)
    db.delete(camera)
    db.commit()
    log_action(db, action="camera.delete", resource_type="camera", actor_user_id=current_user.id, resource_id=camera_id)


@router.post("/{camera_id}/snapshot")
def capture_snapshot(camera_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    # Read frame and write snapshot
    frame = camera_manager.read_frame(camera)
    if frame is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Unable to capture frame from camera")

    snap_key = camera_manager.capture_snapshot(camera_id)
    log_action(db, action="camera.snapshot", resource_type="camera", actor_user_id=current_user.id, resource_id=camera.id)
    return {"snapshot_url": f"/api/v1/stream/snapshot/{snap_key}"}
