"""Frame pipeline: motion gate -> person detector -> face blur.

- motion: frame-difference vs the previous frame (deterministic)
- persons: injectable detector; production default is HOG (CPU, built-in)
- face blur: Haar frontal-face boxes, injected/blurred; the pipeline can
  *withhold* the snapshot when blurring is unavailable — it never stores
  an unblurred face

cv2 is imported lazily so this module stays importable without the wheel.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FrameVerdict:
    motion_score: float  # fraction of pixels noticeably changed, 0..1
    persons: int
    boxes: tuple = ()  # (x, y, w, h) per person


@dataclass(frozen=True)
class PersonEvent:
    person_count: int
    motion_score: float
    snapshot_jpeg: bytes | None
    snapshot_status: str  # stored | withheld-no-detector


def _cv2():  # type: ignore[no-untyped-def]
    import cv2  # local import: available>=4.x only

    return cv2


class HogPersonDetector:
    """CPU person detector (HOG + SVM pedestrian classifier, built into OpenCV)."""

    _instance = None

    def __init__(self) -> None:
        cv2 = _cv2()
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame) -> tuple:  # type: ignore[no-untyped-def]
        _cv2()
        try:
            weights, _rects = self.hog.detectMultiScale(
                frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        except Exception:
            return ()
        return tuple(tuple(int(v) for v in r) for r in (weights or ()))


def detect_faces(frame) -> tuple:  # type: ignore[no-untyped-def]
    """Haar frontal-face boxes. Empty tuple when the detector is unavailable."""
    try:
        cv2 = _cv2()
        cascade_path = os.path.join(
            cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return ()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        return tuple(tuple(int(v) for v in r) for r in faces)
    except Exception:
        return ()  # face-blur unavailable -> caller withholds the snapshot


def blur_boxes(frame, boxes) -> object:  # type: ignore[no-untyped-def]
    """Return a copy with Gaussian-blurred boxes (region content destroyed)."""
    if not boxes:
        return frame
    cv2 = _cv2()
    out = frame.copy()
    h, w = frame.shape[:2]
    for (x, y, bw, bh) in boxes:
        x, y = max(0, x), max(0, y)
        bw, bh = min(bw, w - x), min(bh, h - y)
        if bw <= 2 or bh <= 2:
            continue
        roi = out[y:y + bh, x:x + bw]
        blurred = cv2.GaussianBlur(roi, (21, 21), 0)
        out[y:y + bh, x:x + bw] = blurred
    return out


def motion_score(prev_gray, gray, *, diff_threshold: int = 25) -> float:  # type: ignore[no-untyped-def]
    """Fraction of pixels that changed noticeably. Deterministic."""
    cv2 = _cv2()
    diff = cv2.absdiff(prev_gray, gray)
    _t, mask = cv2.threshold(diff, diff_threshold, 255, cv2.THRESH_BINARY)
    total = mask.size or 1
    return float((mask > 0).sum()) / float(total)


class FrameProcessor:
    """One camera's frame-by-frame decision pipeline."""

    def __init__(self, detector=None) -> None:  # type: ignore[no-untyped-def]
        self._detector = detector if detector is not None else HogPersonDetector()
        self._prev_gray = None
        self._last_person_at = 0.0
        self._snapshot_cooldown_s = 60.0

    def process(self, frame, *, now: float) -> FrameVerdict:
        cv2 = _cv2()
        small = cv2.resize(frame, (640, 480))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        score = 0.0
        if self._prev_gray is not None:
            score = motion_score(self._prev_gray, gray)
        self._prev_gray = gray
        persons = 0
        boxes = ()
        if score > 0.02:  # motion gate: only run the expensive detector then
            boxes = self._detector.detect(small)
            persons = len(boxes)
        return FrameVerdict(score, persons, boxes)

    def make_event(self, frame, verdict: FrameVerdict, *,
                   now: float) -> PersonEvent:
        """Build the stored event, blurring faces; withhold if impossible."""
        cv2 = _cv2()
        small = cv2.resize(frame, (640, 480))
        faces = detect_faces(small)
        if not faces and verdict.persons > 0:
            # persons exist but we cannot prove faces are unknown -> withhold
            # the image entirely and keep metadata only (privacy-first)
            return PersonEvent(verdict.persons, verdict.motion_score,
                               None, "withheld-no-detector")
        if faces:
            small = blur_boxes(small, faces)
        ok, jpeg = cv2.imencode(".jpg", small,
                                [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok:  # pragma: no cover - defensive
            return PersonEvent(verdict.persons, verdict.motion_score,
                               None, "withheld-encode-error")
        return PersonEvent(verdict.persons, verdict.motion_score,
                           jpeg.tobytes(), "stored")
