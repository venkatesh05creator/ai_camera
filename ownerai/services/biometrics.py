"""Biometric enrolment and verification.

The assistant is a *consent based owner verification* system: only people the
owner explicitly enrolled are ever identified, everybody else stays anonymous.

Templates are stored encrypted (AES-GCM) and carry the consent record and a
retention deadline.  Enrolment can be withdrawn at any time, which deletes the
template immediately.

The heavy computer-vision dependencies (TensorFlow Lite / OpenCV) are imported
lazily so that the web application keeps working when they are unavailable.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crypto import decrypt_bytes, encrypt_bytes
from ..models import EnrolledIdentity, User
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_MODEL = "mobile_facenet"

MODEL_INPUT_SIZE = {"facenet": 160, "mobile_facenet": 112}
MODEL_MEAN = {"facenet": 128.0, "mobile_facenet": 127.5}
MODEL_STD = {"facenet": 128.0, "mobile_facenet": 127.5}
#: Output dimensions of the bundled models (verified against the .tflite files).
MODEL_DIM = {"facenet": 512, "mobile_facenet": 192}

_INTERPRETERS: dict[str, Any] = {}


class BiometricsError(RuntimeError):
    """Generic biometric failure - safe to show a short message."""


class BiometricsUnavailable(BiometricsError):
    """Raised when the vision stack or the model file is missing."""


class EnrollmentRejected(BiometricsError):
    """Raised when no usable face could be extracted from the supplied images."""


def model_path(model_name: str = DEFAULT_MODEL) -> str:
    """Resolve the path of a TFLite model inside the project."""
    filename = "facenet-2.tflite" if model_name == "facenet" else "mobile_face_net.tflite"
    return os.path.join(PROJECT_ROOT, "models", filename)


def cascade_path() -> str:
    return os.path.join(PROJECT_ROOT, "models", "haarcascade_frontalface_default.xml")


def is_available(model_name: str = DEFAULT_MODEL) -> bool:
    """Return ``True`` when the model and the cascade are present on disk."""
    return os.path.isfile(model_path(model_name)) and os.path.isfile(cascade_path())


def _get_interpreter(model_name: str):
    """Return (and cache) a TFLite interpreter for the given model."""
    if model_name in _INTERPRETERS:
        return _INTERPRETERS[model_name]

    path = model_path(model_name)
    if not os.path.isfile(path):
        raise BiometricsUnavailable("the biometric model is not installed on this server")

    try:  # pragma: no cover - depends on the optional vision stack
        import tensorflow as tf
    except Exception as exc:  # pragma: no cover
        raise BiometricsUnavailable("the vision stack is not available") from exc

    try:  # pragma: no cover
        interpreter = tf.lite.Interpreter(model_path=path)
        interpreter.allocate_tensors()
    except Exception as exc:  # pragma: no cover
        raise BiometricsUnavailable("the biometric model could not be loaded") from exc

    _INTERPRETERS[model_name] = interpreter
    return interpreter


def decode_image(payload: bytes):
    """Decode raw image bytes into an OpenCV image."""
    try:  # pragma: no cover - depends on the optional vision stack
        import cv2
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise BiometricsUnavailable("the vision stack is not available") from exc

    array = np.frombuffer(payload, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise EnrollmentRejected("the uploaded file is not a readable image")
    return image


def decode_data_url(payload: str) -> bytes:
    """Decode a base64 (optionally data-URL) encoded image."""
    if not payload:
        raise EnrollmentRejected("empty image payload")
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EnrollmentRejected("the image is not valid base64 data") from exc


def detect_faces(image) -> List[Tuple[int, int, int, int]]:
    """Detect faces in an image using the bundled Haar cascade."""
    try:  # pragma: no cover - depends on the optional vision stack
        import cv2
    except Exception as exc:  # pragma: no cover
        raise BiometricsUnavailable("the vision stack is not available") from exc

    if not os.path.isfile(cascade_path()):
        raise BiometricsUnavailable("the face detector is not installed on this server")
    cascade = cv2.CascadeClassifier(cascade_path())
    if cascade.empty():  # pragma: no cover - broken installation
        raise BiometricsUnavailable("the face detector could not be loaded")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    return [tuple(int(value) for value in face) for face in faces]


def compute_embedding(image, model_name: str = DEFAULT_MODEL):
    """Compute a normalised face embedding for the largest detected face."""
    try:  # pragma: no cover - depends on the optional vision stack
        import cv2
        import numpy as np
    except Exception as exc:  # pragma: no cover
        raise BiometricsUnavailable("the vision stack is not available") from exc

    faces = detect_faces(image)
    if not faces:
        raise EnrollmentRejected("no face could be detected in the supplied image")

    x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
    roi = image[y : y + h, x : x + w]
    if roi.size == 0:  # pragma: no cover - defensive
        raise EnrollmentRejected("the detected face region was empty")

    size = MODEL_INPUT_SIZE.get(model_name, 112)
    mean = MODEL_MEAN.get(model_name, 127.5)
    std = MODEL_STD.get(model_name, 127.5)

    resized = cv2.resize(roi, (size, size))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalised = (rgb.astype("float32") - mean) / std
    batch = np.expand_dims(normalised, axis=0)

    interpreter = _get_interpreter(model_name)
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    expected_dtype = input_details[0]["dtype"]
    if batch.dtype != expected_dtype:
        batch = batch.astype(expected_dtype)
    interpreter.set_tensor(input_details[0]["index"], batch)
    interpreter.invoke()
    embedding = interpreter.get_tensor(output_details[0]["index"])[0]
    norm = np.linalg.norm(embedding)
    if not np.isfinite(norm) or norm == 0:
        raise EnrollmentRejected("the embedding could not be computed")
    return embedding / norm


def cosine_similarity(left, right) -> float:
    """Cosine similarity of two embeddings."""
    import numpy as np

    left = np.asarray(left, dtype="float64").ravel()
    right = np.asarray(right, dtype="float64").ravel()
    if left.shape != right.shape:
        return 0.0
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator == 0:
        return 0.0
    return float(np.dot(left, right) / denominator)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def _encrypt_template(embedding, settings: Optional[Settings] = None) -> bytes:
    payload = ",".join(f"{value:.6f}" for value in embedding.tolist())
    return encrypt_bytes(payload.encode("utf-8"), aad=b"biometric-template")


def _decrypt_template(blob: bytes) -> List[float]:
    raw = decrypt_bytes(blob, aad=b"biometric-template").decode("utf-8")
    return [float(value) for value in raw.split(",") if value != ""]


def enroll_identity(
    db: Session,
    user: User,
    *,
    label: str,
    images: List[str],
    consent: bool,
    settings: Optional[Settings] = None,
) -> EnrolledIdentity:
    """Enrol a consented identity for the given owner."""
    settings = settings or get_settings()
    if not settings.biometrics_enabled:
        raise BiometricsError("biometric enrolment is disabled on this deployment")
    if not consent:
        raise BiometricsError("explicit consent is required to store a biometric template")
    if not images:
        raise EnrollmentRejected("at least one image is required")
    if len(images) > settings.enrollment_max_images:
        raise EnrollmentRejected("too many images in a single enrolment request")

    embeddings = []
    for payload in images:
        raw = decode_data_url(payload)
        image = decode_image(raw)
        embeddings.append(compute_embedding(image))

    import numpy as np

    stacked = np.stack(embeddings, axis=0)
    average = stacked.mean(axis=0)
    norm = np.linalg.norm(average)
    if not np.isfinite(norm) or norm == 0:
        raise EnrollmentRejected("the averaged embedding is invalid")
    average = average / norm

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.biometric_retention_days)

    existing = db.scalar(
        select(EnrolledIdentity).where(
            EnrolledIdentity.owner_id == user.id, EnrolledIdentity.label == label
        )
    )
    if existing is not None:
        existing.template_encrypted = _encrypt_template(average, settings)
        existing.model_name = DEFAULT_MODEL
        existing.embedding_dim = int(average.shape[0])
        existing.consent_at = now
        existing.consent_version = "1"
        existing.expires_at = expires_at
        existing.withdrawn_at = None
        db.commit()
        db.refresh(existing)
        return existing

    identity = EnrolledIdentity(
        owner_id=user.id,
        label=label,
        model_name=DEFAULT_MODEL,
        embedding_dim=int(average.shape[0]),
        template_encrypted=_encrypt_template(average, settings),
        consent_at=now,
        consent_version="1",
        expires_at=expires_at,
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def withdraw_identity(db: Session, user: User, identity: EnrolledIdentity) -> None:
    """Withdraw consent and delete the stored template."""
    identity.withdrawn_at = datetime.now(timezone.utc)
    identity.template_encrypted = encrypt_bytes(b"", aad=b"biometric-template")
    identity.expires_at = datetime.now(timezone.utc)
    db.commit()


def verify_owner(
    db: Session,
    user: User,
    image_payload: str,
    *,
    settings: Optional[Settings] = None,
) -> dict:
    """Verify that the person in front of the camera is the enrolled owner.

    Only the caller's own templates are compared.  A person who was never
    enrolled stays anonymous - the function reports ``matched=False`` and never
    reveals any identity.
    """
    settings = settings or get_settings()
    raw = decode_data_url(image_payload)
    image = decode_image(raw)
    embedding = compute_embedding(image)

    templates = db.scalars(
        select(EnrolledIdentity).where(
            EnrolledIdentity.owner_id == user.id, EnrolledIdentity.withdrawn_at.is_(None)
        )
    ).all()

    best_label = None
    best_score = 0.0
    for template in templates:
        if template.expires_at is not None:
            expires = template.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= datetime.now(timezone.utc):
                continue
        try:
            stored = _decrypt_template(template.template_encrypted)
        except Exception:
            logger.warning("skipping unreadable biometric template", extra={"identity_id": template.id})
            continue
        score = cosine_similarity(embedding, stored)
        if score > best_score:
            best_score = score
            best_label = template.label

    matched = best_label is not None and best_score >= settings.face_match_threshold
    return {
        "matched": matched,
        "label": best_label if matched else None,
        "confidence": round(best_score, 4),
        "threshold": settings.face_match_threshold,
    }


def purge_expired_templates(db: Session, settings: Optional[Settings] = None) -> int:
    """Delete templates whose retention period has expired."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    removed = 0
    for template in db.scalars(select(EnrolledIdentity)).all():
        expires = template.expires_at
        if expires is None:
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= now:
            template.template_encrypted = encrypt_bytes(b"", aad=b"biometric-template")
            template.withdrawn_at = now
            removed += 1
    db.commit()
    return removed


def read_image_file(path: str) -> bytes:
    """Helper for CLI tooling and tests."""
    with open(path, "rb") as handle:
        return handle.read()


def image_to_data_url(raw: bytes) -> str:
    """Encode raw image bytes as a data URL."""
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
