"""Compatibility endpoints for the original face-embedding prototype.

The prototype exposed an unauthenticated endpoint that read *any* path on the
server and returned embeddings for it.  The functionality is preserved, but the
endpoint now

* requires an authenticated, authorised account,
* only accepts files inside an explicitly allowed directory,
* never returns a stack trace, and
* is rate limited.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..models import User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import DEVICE_READ, has_permission
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/legacy", tags=["legacy"])

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _allowed_root() -> str:
    """Return the directory the endpoint is allowed to read from."""
    root = os.environ.get("OWNERAI_LEGACY_IMAGE_ROOT", "")
    if not root:
        root = os.path.join(os.getcwd(), "inputs")
    return os.path.realpath(root)


def _resolve_image(raw_path: str) -> str:
    """Resolve a user supplied path and make sure it stays inside the root."""
    if not raw_path:
        raise HTTPException(status_code=422, detail="an image path is required")
    if len(raw_path) > 1024:
        raise HTTPException(status_code=422, detail="invalid image path")

    root = _allowed_root()
    candidate = raw_path if os.path.isabs(raw_path) else os.path.join(root, raw_path)
    resolved = os.path.realpath(candidate)
    if resolved != root and not resolved.startswith(root + os.sep):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the requested file is outside the allowed directory",
        )
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="the image was not found")
    if os.path.splitext(resolved)[1].lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported image format",
        )
    return resolved


@router.post("/embeddings")
def extract_embeddings(
    request: Request,
    model_name: str = Query(default="facenet", max_length=64),
    image_path: str = Query(default="", max_length=1024),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> Dict[str, Any]:
    """Extract face embeddings from an image that lives inside the allowed directory."""
    if not has_permission(user.role, DEVICE_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "legacy_embeddings",
            f"user:{user.id}",
            settings.upload_rate_limit,
            settings.upload_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many requests, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    resolved = _resolve_image(image_path)

    try:
        import cv2

        from face_add_static import extract_face_embeddings_from_image
        from utils.face_utils import image_to_base64
    except Exception:  # pragma: no cover - optional vision stack
        logger.warning("the vision stack is not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the vision stack is not available on this server",
        ) from None

    image = cv2.imread(resolved)
    if image is None:
        raise HTTPException(status_code=422, detail="the image could not be read")
    encoded = image_to_base64(image)

    try:
        embedding, status_message = extract_face_embeddings_from_image(model_name, encoded)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="unknown model configuration"
        ) from None
    except Exception:
        logger.exception("embedding extraction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="the embeddings could not be extracted",
        ) from None

    if embedding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=status_message or "no face detected")

    return {
        "embedding": embedding.tolist(),
        "model_name": model_name,
        "dimensions": int(embedding.shape[0]),
    }
