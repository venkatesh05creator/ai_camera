"""Live-feed analysis for the monitoring console.

The console shows live statistics about the camera feed.  They are computed
from the *owner's own* frames:

* the number of faces in the frame,
* whether the frame matches one of the owner's enrolled templates.

Strangers are never identified: the response only contains a count and, at
most, the label of the owner's own template.  Raw frames are analysed in the
request and are never stored.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import EVENT_READ, has_permission
from ..schemas import StrictModel
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vision", tags=["vision"])


class AnalyseRequest(StrictModel):
    """A single frame of the live feed."""

    image: str = Field(min_length=16, max_length=8 * 1024 * 1024)


@router.post("/analyse")
def analyse_frame(
    payload: AnalyseRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
    _: None = Depends(enforce_csrf),
) -> Dict[str, Any]:
    """Analyse one frame and return anonymous telemetry."""
    if not has_permission(user.role, EVENT_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "vision",
            f"user:{user.id}",
            settings.upload_rate_limit,
            settings.upload_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many analysis requests, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    from ..services import biometrics

    try:
        raw = biometrics.decode_data_url(payload.image)
        image = biometrics.decode_image(raw)
        faces = biometrics.detect_faces(image)
    except biometrics.BiometricsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except biometrics.EnrollmentRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    confidence: Optional[float] = None
    owner_match = False
    label: Optional[str] = None

    if faces:
        try:
            embedding = biometrics.compute_embedding(image)
            best_label, best_score = _best_owner_match(db, user, embedding, settings)
            confidence = round(float(best_score), 4)
            owner_match = best_label is not None and confidence >= settings.face_match_threshold
            label = best_label if owner_match else None
        except biometrics.BiometricsUnavailable:
            raise
        except Exception:  # pragma: no cover - analysis must not break the feed
            logger.warning("frame analysis failed", exc_info=False)

    return {
        "faces": len(faces),
        "owner_match": owner_match,
        "label": label,
        "confidence": confidence,
        "engine": _engine_name(),
        "threshold": settings.face_match_threshold,
    }


def _best_owner_match(db: Session, user: User, embedding, settings) -> tuple[Optional[str], float]:
    """Compare a frame with the owner's own templates only."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from ..models import EnrolledIdentity

    best_label: Optional[str] = None
    best_score = 0.0
    templates = db.scalars(
        select(EnrolledIdentity).where(
            EnrolledIdentity.owner_id == user.id, EnrolledIdentity.withdrawn_at.is_(None)
        )
    ).all()
    now = datetime.now(timezone.utc)
    for template in templates:
        if template.expires_at is not None:
            expires = template.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= now:
                continue
        try:
            stored = biometrics_decrypt(template.template_encrypted)
        except Exception as exc:
            logger.warning("Failed to decrypt biometric template %s: %s", template.id, exc)
            continue
        score = biometrics_cosine(embedding, stored)
        if score > best_score:
            best_score = score
            best_label = template.label
    return best_label, best_score


def biometrics_decrypt(blob: bytes) -> List[float]:
    from ..services.biometrics import _decrypt_template

    return _decrypt_template(blob)


def biometrics_cosine(embedding, stored: List[float]) -> float:
    from ..services.biometrics import cosine_similarity

    return cosine_similarity(embedding, stored)


def _engine_name() -> str:
    """The name of the recognition engine that is installed."""
    from ..services.biometrics import DEFAULT_MODEL, is_available

    if not is_available():
        return "not installed"
    if DEFAULT_MODEL == "mobile_facenet":
        return "MobileFaceNet 192-Dim"
    return "FaceNet 512-Dim"
