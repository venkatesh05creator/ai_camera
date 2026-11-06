"""Face engine: SCRFD detection + ArcFace embeddings (InsightFace, offline).

Enrolled-person identification ONLY:
- the engine never labels a face without a threshold match against an
  enrolled template (anything below threshold is "unknown" with its
  best score reported — a label is never invented)
- stranger faces get no identity, ever (no gallery, no clustering)

The real engine lazily loads ``buffalo_sc`` ONNX models. Tests inject a
deterministic fake through :func:`get_engine` for full-flow verification.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import numpy as np

ENABLED_DEFAULT_THRESHOLD = 0.35


@dataclass(frozen=True)
class FaceReading:
    box: tuple[int, int, int, int]
    embedding: np.ndarray
    quality: float  # detector score 0..1


class FaceEngineNotInstalled(Exception):
    pass


class InsightFaceEngine:
    """Production engine backed by InsightFace (SCRFD + ArcFace, CPU)."""

    def __init__(self, model_dir: str, model_name: str = "buffalo_sc") -> None:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name=model_name, root=model_dir,
                           providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        self._app = app
        self._lock = threading.Lock()

    def read_faces(self, frame: np.ndarray) -> list[FaceReading]:
        with self._lock:
            faces = self._app.get(frame)
        out = []
        for face in faces:
            emb = np.asarray(face.embedding, dtype=np.float32)
            norm = float(np.linalg.norm(emb))
            quality = float(getattr(face, "det_score", 0.0) or 0.0)
            out.append(FaceReading(
                box=(int(face.bbox[0]), int(face.bbox[1]),
                     int(face.bbox[2]) - int(face.bbox[0]),
                     int(face.bbox[3]) - int(face.bbox[1])),
                embedding=emb / norm if norm > 0 else emb,
                quality=quality))
        return out

    @staticmethod
    def average(samples: list[np.ndarray]) -> np.ndarray:
        stacked = np.stack(samples)
        mean = stacked.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        return mean / norm if norm > 0 else mean


# --------------------------------------------------------------- matching
def identify(
    embedding: np.ndarray,
    templates: list[tuple[int, np.ndarray]],
    *,
    threshold: float,
) -> tuple[int | None, float]:
    """Best enrolled match, or (None, best_score) when it is not a match."""
    best_id, best_score = None, -1.0
    for person_id, template in templates:
        score = float(embedding @ template)
        if score > best_score:
            best_id, best_score = person_id, score
    if best_id is not None and best_score >= threshold:
        return best_id, best_score
    return None, best_score


# ------------------------------------------------------------------ engine
_engine_lock = threading.Lock()
_engine: InsightFaceEngine | None = None
_engine_error: str | None = None


def get_engine(settings) -> InsightFaceEngine:  # type: ignore[no-untyped-def]
    """Lazy singleton; raises FaceEngineNotInstalled with the real cause."""
    global _engine, _engine_error
    if _engine is not None:
        return _engine
    if _engine_error is not None:
        raise FaceEngineNotInstalled(_engine_error)
    with _engine_lock:
        if _engine is not None:
            return _engine
        target = os.path.join(settings.face_model_dir, settings.face_model_name)
        if not os.path.isdir(target):
            _engine_error = (
                f"face models missing at {target} (download buffalo_sc or "
                "set OWNERAI_FACE_MODEL_DIR)")
            raise FaceEngineNotInstalled(_engine_error)
        try:
            _engine = InsightFaceEngine(settings.face_model_dir,
                                        settings.face_model_name)
        except Exception as exc:  # noqa: BLE001
            _engine_error = f"face engine failed to load: {type(exc).__name__}"
            raise FaceEngineNotInstalled(_engine_error) from exc
        return _engine


def reset_engine() -> None:
    """Test hook to drop the cached engine instance."""
    global _engine, _engine_error
    _engine = None
    _engine_error = None


def engine_available(settings) -> bool:  # type: ignore[no-untyped-def]
    try:
        get_engine(settings)
        return True
    except FaceEngineNotInstalled:
        return False
