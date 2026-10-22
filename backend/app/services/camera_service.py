"""Camera ingestion service: handles webcams, IP cameras, and RTSP streams."""

from __future__ import annotations

import base64
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.entities import Camera


class CameraStreamManager:
    """Manages active video feeds with dedicated background frame grabber threads.
    
    Continuously drains hardware webcam and IP/RTSP streams at full speed with:
    - Zero DirectShow / network frame buffering latency
    - Bounded exponential backoff with jitter on disconnects
    - Multi-camera health telemetry (FPS, resolution, last frame time, connection state)
    - Complete worker isolation (one failing feed never blocks or affects others)
    """

    def __init__(self):
        self.active_captures: Dict[str, cv2.VideoCapture] = {}
        self.latest_frames: Dict[str, np.ndarray] = {}
        self.frame_timestamps: Dict[str, float] = {}
        self.grabber_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        self.camera_health: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _grabber_loop(self, cid: str, source: int | str, api_pref: int, stop_event: threading.Event):
        """Dedicated high-speed thread with bounded exponential backoff auto-reconnect."""
        import random
        attempts = 0
        consecutive_failures = 0
        frame_count = 0
        fps_timer = time.time()

        while not stop_event.is_set():
            # Check or establish capture connection
            cap: Optional[cv2.VideoCapture] = None
            with self.lock:
                cap = self.active_captures.get(cid)

            if cap is None or not cap.isOpened():
                with self.lock:
                    self.camera_health[cid]["status"] = "reconnecting" if attempts > 0 else "connecting"
                    self.camera_health[cid]["reconnect_attempts"] = attempts

                # Bounded exponential backoff with jitter
                backoff = min(30.0, (1.5 ** min(attempts, 8)) + random.uniform(0.1, 0.6))
                time.sleep(backoff)

                try:
                    new_cap = cv2.VideoCapture(source, api_pref) if api_pref != cv2.CAP_ANY else cv2.VideoCapture(source)
                    if new_cap.isOpened():
                        new_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                        new_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                        new_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        with self.lock:
                            self.active_captures[cid] = new_cap
                            self.camera_health[cid]["status"] = "online"
                            self.camera_health[cid]["consecutive_errors"] = 0
                        attempts = 0
                        consecutive_failures = 0
                        cap = new_cap
                    else:
                        attempts += 1
                        continue
                except Exception as e:
                    attempts += 1
                    with self.lock:
                        self.camera_health[cid]["last_error"] = str(e)
                    continue

            # Frame grabbing loop
            try:
                ret, frame = cap.read()
                now = time.time()
                if ret and frame is not None and frame.size > 0:
                    with self.lock:
                        self.latest_frames[cid] = frame
                        self.frame_timestamps[cid] = now
                        h, w = frame.shape[:2]
                        health = self.camera_health.setdefault(cid, {})
                        health["status"] = "online"
                        health["last_frame_timestamp"] = now
                        health["resolution"] = f"{w}x{h}"
                        health["consecutive_errors"] = 0

                    consecutive_failures = 0
                    frame_count += 1
                    if now - fps_timer >= 1.0:
                        with self.lock:
                            self.camera_health[cid]["fps"] = round(frame_count / (now - fps_timer), 1)
                        frame_count = 0
                        fps_timer = now
                else:
                    consecutive_failures += 1
                    if consecutive_failures > 30:
                        # Feed considered disconnected
                        with self.lock:
                            self.camera_health[cid]["status"] = "offline"
                            self.camera_health[cid]["consecutive_errors"] = consecutive_failures
                            if cid in self.active_captures:
                                try:
                                    self.active_captures[cid].release()
                                except Exception:
                                    pass
                                del self.active_captures[cid]
                        attempts += 1
                        time.sleep(0.5)
                    else:
                        time.sleep(0.02)
            except Exception as e:
                consecutive_failures += 1
                with self.lock:
                    self.camera_health[cid]["last_error"] = str(e)
                time.sleep(0.05)

            time.sleep(0.003)  # Yield slightly, draining cleanly at up to 60 FPS

    def get_or_open_capture(self, camera: Union[Camera, str]) -> Optional[cv2.VideoCapture]:
        with self.lock:
            try:
                if isinstance(camera, str):
                    cid = camera
                    source_type = "webcam"
                    stream_url = "0"
                    cam_name = cid[:8]
                    resolution = "1280x720"
                else:
                    cid = camera.id
                    source_type = camera.source_type
                    stream_url = camera.stream_url
                    cam_name = camera.name
                    resolution = camera.resolution or "1280x720"
            except Exception:
                return None

            if cid in self.active_captures and self.active_captures[cid].isOpened():
                return self.active_captures[cid]

            # Determine source
            source: int | str = 0
            api_pref = cv2.CAP_ANY
            if source_type == "webcam":
                try:
                    source = int(stream_url) if stream_url and str(stream_url).isdigit() else 0
                except (ValueError, TypeError):
                    source = 0
                if os.name == "nt":
                    api_pref = cv2.CAP_DSHOW
            else:
                source = stream_url or 0

            # Initialize health entry
            if cid not in self.camera_health:
                self.camera_health[cid] = {
                    "camera_id": cid,
                    "name": cam_name,
                    "source_type": source_type,
                    "status": "connecting",
                    "fps": 0.0,
                    "resolution": resolution,
                    "last_frame_timestamp": 0.0,
                    "reconnect_attempts": 0,
                    "consecutive_errors": 0,
                }

            # Start background grabber thread if not already running
            if cid not in self.grabber_threads or not self.grabber_threads[cid].is_alive():
                stop_event = threading.Event()
                self.stop_events[cid] = stop_event
                t = threading.Thread(
                    target=self._grabber_loop,
                    args=(cid, source, api_pref, stop_event),
                    daemon=True,
                    name=f"Grabber-{cid[:8]}",
                )
                self.grabber_threads[cid] = t
                t.start()

            # Return active capture if opened by grabber
            return self.active_captures.get(cid)

    def read_frame(self, camera: Union[Camera, str]) -> Optional[np.ndarray]:
        try:
            if isinstance(camera, str):
                cid = camera
            else:
                cid = camera.id
        except Exception:
            return None

        self.get_or_open_capture(camera)

        with self.lock:
            frame = self.latest_frames.get(cid)
            if frame is not None:
                return frame.copy()
        return None

    def get_latest_frame(self, camera_id: str) -> Optional[np.ndarray]:
        with self.lock:
            frame = self.latest_frames.get(camera_id)
            return frame.copy() if frame is not None else None

    def get_camera_health(self, camera_id: str) -> Dict[str, Any]:
        with self.lock:
            health = self.camera_health.get(camera_id, {
                "camera_id": camera_id,
                "status": "offline",
                "fps": 0.0,
                "resolution": "1280x720",
                "last_frame_timestamp": 0.0,
                "is_stale": True,
            })
            now = time.time()
            last_ts = self.frame_timestamps.get(camera_id, 0.0)
            is_stale = (now - last_ts) > 3.0 if last_ts > 0 else True
            health["is_stale"] = is_stale
            if is_stale and health.get("status") == "online":
                health["status"] = "stale"
            return health.copy()

    def capture_snapshot(self, camera_id: str) -> Optional[str]:
        """Save a snapshot of the current frame to disk and return relative object key."""
        with self.lock:
            frame = self.latest_frames.get(camera_id)
        if frame is None:
            return None

        settings = get_settings()
        now = datetime.now(timezone.utc)
        filename = f"snap_{camera_id[:8]}_{int(now.timestamp())}.jpg"
        filepath = settings.snapshot_storage_path / filename

        cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return filename

    def release_camera(self, camera_id: str) -> None:
        with self.lock:
            if camera_id in self.stop_events:
                self.stop_events[camera_id].set()
                del self.stop_events[camera_id]
            if camera_id in self.grabber_threads:
                del self.grabber_threads[camera_id]
            if camera_id in self.active_captures:
                try:
                    self.active_captures[camera_id].release()
                except Exception:
                    pass
                del self.active_captures[camera_id]
            if camera_id in self.latest_frames:
                del self.latest_frames[camera_id]
            if camera_id in self.frame_timestamps:
                del self.frame_timestamps[camera_id]
            if camera_id in self.camera_health:
                self.camera_health[camera_id]["status"] = "offline"


camera_manager = CameraStreamManager()



def ensure_default_webcam(db: Session, user_id: str) -> Optional[Camera]:
    """Ensure at least one default laptop webcam is registered if database has no cameras."""
    existing = db.scalars(select(Camera)).first()
    if existing:
        return existing

    cam = Camera(
        name="Laptop Primary Webcam",
        source_type="webcam",
        location_label="Workstation / Laptop",
        status="online",
        stream_url="0",
        owner_user_id=user_id,
        fps=30.0,
        resolution="1280x720",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam
