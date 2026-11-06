"""Camera workers: live capture loop (thread per camera).

Each worker:
- opens its source (webcam index / RTSP URL)
- runs the FrameProcessor at ~2 FPS (detection is motion-gated)
- on person events: records + notifies + updates health
- on read failure: health becomes error/offline with the real cause and
  the loop retries (honest status, no silent hangs)

Workers talk to SQLite through the stdlib ``sqlite3`` module because the
async engine is bound to the app's event loop; this keeps worker writes
loop-free and just as consistent (same file, WAL, short transactions).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time

from ..config import Settings
from ..models.user import utcnow
from ..security.crypto import encrypt_text
from ..services.memory_service import memory_key
from ..vision.pipeline import FrameProcessor

logger = logging.getLogger(__name__)


def _db_path(settings: Settings) -> str:
    url = settings.database_url
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            return url[len(prefix):] or "var/aegis.db"
    raise RuntimeError("camera workers require a sqlite database_url")


def _connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    return con


class CameraWorker(threading.Thread):
    def __init__(self, camera, factory, settings: Settings,
                 processor: FrameProcessor | None = None) -> None:
        super().__init__(daemon=True, name=f"camera-{camera.id}")
        self.camera_id = camera.id
        self.source = camera.source
        self.kind = camera.kind
        self.settings = settings
        self.processor = processor or FrameProcessor()
        self._stop = threading.Event()
        self._db_path = _db_path(settings)

    def stop(self) -> None:
        self._stop.set()

    def _face_labels(self, frame) -> str | None:  # type: ignore[no-untyped-def]
        """Identify enrolled faces; returns plaintext labels JSON or None.

        Faces found but no engine/templates -> None ("unknown" is the
        default verdict: identification is never guessed).
        """
        import json

        from ..vision.face import FaceEngineNotInstalled, get_engine, identify

        try:
            engine = get_engine(self.settings)
        except FaceEngineNotInstalled:
            return None
        from ..security.crypto import decrypt_text
        from ..services.memory_service import memory_key

        try:
            con = _connect(self._db_path)
            rows = con.execute(
                "SELECT face_templates.embedding_encrypted, people.id,"
                " people.name FROM face_templates"
                " JOIN people ON people.id=face_templates.person_id").fetchall()
            con.close()
        except Exception:
            logger.exception("camera %s template load failed", self.camera_id)
            return None
        if not rows:
            return None
        key = memory_key(self.settings)
        templates = []
        names = {}
        import numpy as np
        for encrypted, pid, name in rows:
            try:
                vec = np.array(json.loads(decrypt_text(key, encrypted)),
                               dtype=np.float32)
            except Exception as exc:
                logger.warning("skipping undecryptable template: %s",
                               type(exc).__name__)
                continue
            norm = float(np.linalg.norm(vec))
            if norm > 0:
                templates.append((pid, vec / norm))
                names[pid] = name
        faces = engine.read_faces(frame)
        if not faces:
            return None
        known = []
        unknown = 0
        for face in faces:
            pid, score = identify(face.embedding, templates,
                                  threshold=self.settings.face_match_threshold)
            if pid is not None:
                known.append({"person_id": pid, "name": names.get(pid, "?"),
                              "score": round(score, 3)})
            else:
                unknown += 1
        return json.dumps({"known": known, "unknown_faces": unknown})

    def _set_health(self, *, status: str, error: str | None) -> None:
        try:
            con = _connect(self._db_path)
        except Exception:
            logger.exception("camera %s db connect failed", self.camera_id)
            return
        try:
            now = utcnow().isoformat(sep=" ")
            con.execute(
                "UPDATE camera_health SET status=?, error=?, updated_at=?"
                " WHERE camera_id=?",
                (status, error, now, self.camera_id))
            con.commit()
        except Exception:
            logger.exception("camera %s health update failed", self.camera_id)
        finally:
            con.close()

    def _mark_frame(self, fps: float) -> None:
        try:
            con = _connect(self._db_path)
        except Exception:
            logger.exception("camera %s db connect failed", self.camera_id)
            return
        try:
            now = utcnow().isoformat(sep=" ")
            con.execute(
                "UPDATE camera_health SET status='online', error=NULL,"
                " last_frame_at=?, fps=?, frames=frames+1, updated_at=?"
                " WHERE camera_id=?",
                (now, round(fps, 2), now, self.camera_id))
            con.commit()
        except Exception:
            logger.exception("camera %s frame mark failed", self.camera_id)
        finally:
            con.close()

    def _record_person(self, frame, verdict, now: float) -> None:  # type: ignore[no-untyped-def]
        event = self.processor.make_event(frame, verdict, now=now)
        key = memory_key(self.settings)
        snapshot = (encrypt_text(key, event.snapshot_jpeg.decode("latin-1"))
                    if event.snapshot_jpeg else None)
        labels_plain = self._face_labels(frame)
        labels = (encrypt_text(key, labels_plain)
                  if labels_plain else None)
        try:
            con = _connect(self._db_path)
        except Exception:
            logger.exception("camera %s db connect failed", self.camera_id)
            return
        try:
            ts = utcnow().isoformat(sep=" ")
            con.execute(
                "INSERT INTO camera_events (camera_id, ts, kind, person_count,"
                " motion_score, snapshot_encrypted, snapshot_status,"
                " labels_encrypted) VALUES (?, ?, 'person', ?, ?, ?, ?, ?)",
                (self.camera_id, ts, event.person_count,
                 event.motion_score, snapshot, event.snapshot_status, labels))
            con.execute(
                "UPDATE camera_health SET last_event_at=?, updated_at=?"
                " WHERE camera_id=?", (ts, ts, self.camera_id))
            con.execute(
                "INSERT INTO notifications (ts, camera_id, kind, title, body,"
                " is_read) VALUES (?, ?, 'person', ?, ?, 0)",
                (ts, self.camera_id,
                 f"Person seen on camera {self.camera_id}",
                 f"{event.person_count} person(s) detected (motion "
                 f"{event.motion_score:.1%}); snapshot "
                 f"{event.snapshot_status}"))
            con.commit()
        except Exception:
            logger.exception("camera %s event persist failed", self.camera_id)
        finally:
            con.close()

    def run_once(self, frame, *, now: float) -> None:
        """One frame through the pipeline (test hook + worker reuse)."""
        verdict = self.processor.process(frame, now=now)
        if verdict.persons > 0:
            self._record_person(frame, verdict, now)

    def run(self) -> None:  # pragma: no cover - manual hardware loop
        import cv2

        source: str | int
        if self.kind == "webcam":
            try:
                source = int(self.source or "0")
            except ValueError:
                source = 0
        else:
            source = self.source
        capture = None
        try:
            capture = cv2.VideoCapture(source)
        except Exception as exc:  # noqa: BLE001
            self._set_health(status="error",
                             error=f"open failed: {exc}"[:300])
            capture = None
        tries = 0
        try:
            while not self._stop.is_set():
                if capture is None or not capture.isOpened():
                    self._set_health(status="error",
                                     error=f"cannot open source ({self.source})")
                    self._stop.wait(5.0)
                    capture = cv2.VideoCapture(source)
                    continue
                ok, frame = capture.read()
                if not ok or frame is None:
                    self._set_health(status="error",
                                     error="no frame from source")
                    self._stop.wait(1.0)
                    continue
                tries += 1
                started = time.time()
                self.run_once(frame, now=started)
                elapsed = max(time.time() - started, 1e-3)
                self._mark_frame(1.0 / elapsed)
                self._stop.wait(0.5)  # ~2 FPS budget for detection loops
        finally:
            if capture is not None:
                capture.release()


class CameraManager:
    """Owns all workers; lifecycle is driven by the API."""

    def __init__(self) -> None:
        self._workers: dict[int, CameraWorker] = {}
        self._lock = threading.Lock()

    def start(self, camera, factory, settings: Settings) -> bool:
        with self._lock:
            if camera.id in self._workers:
                return False
            worker = CameraWorker(camera, factory, settings)
            self._workers[camera.id] = worker
            worker.start()
            return True

    def stop(self, camera_id: int) -> bool:
        with self._lock:
            worker = self._workers.pop(camera_id, None)
        if worker is None:
            return False
        worker.stop()
        worker.join(timeout=3.0)
        return True

    def is_running(self, camera_id: int) -> bool:
        with self._lock:
            worker = self._workers.get(camera_id)
        return bool(worker and worker.is_alive())


manager = CameraManager()
