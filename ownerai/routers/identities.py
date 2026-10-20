"""Biometric enrolment and owner verification endpoints."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import EnrolledIdentity, User
from ..rbac import IDENTITY_DELETE, IDENTITY_READ, IDENTITY_WRITE, has_permission
from ..schemas import IdentityEnroll, IdentityOut
from ..services import audit
from ..services.biometrics import (
    BiometricsError,
    BiometricsUnavailable,
    EnrollmentRejected,
    enroll_identity,
    is_available,
    verify_owner,
    withdraw_identity,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identities", tags=["identities"])


@router.get("", response_model=List[IdentityOut])
def list_identities(
    db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> List[IdentityOut]:
    """List the identities the owner enrolled."""
    if not has_permission(user.role, IDENTITY_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    identities = db.scalars(
        select(EnrolledIdentity)
        .where(EnrolledIdentity.owner_id == user.id)
        .order_by(EnrolledIdentity.id)
    ).all()
    return [IdentityOut.model_validate(identity) for identity in identities]


@router.post("", response_model=IdentityOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(enforce_csrf)])
def enroll(
    payload: IdentityEnroll,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> IdentityOut:
    """Enrol a biometric template.  Explicit consent is mandatory."""
    if not has_permission(user.role, IDENTITY_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    if not payload.consent:
        raise HTTPException(
            status_code=422,
            detail="explicit consent is required to store a biometric template",
        )
    if not is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the biometric engine is not installed on this server",
        )
    try:
        identity = enroll_identity(
            db, user, label=payload.label, images=payload.images, consent=payload.consent
        )
    except EnrollmentRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BiometricsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except BiometricsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit.record(
        db,
        action="identity.enroll",
        actor_user_id=user.id,
        target_type="identity",
        target_id=identity.id,
        ip=_client_ip(request),
        detail={"label": identity.label, "consent_version": identity.consent_version},
    )
    return IdentityOut.model_validate(identity)


@router.delete("/{identity_id}", dependencies=[Depends(enforce_csrf)])
def withdraw(
    identity_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Withdraw consent: the stored template is deleted immediately."""
    identity = db.get(EnrolledIdentity, identity_id)
    if identity is None or identity.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if not has_permission(user.role, IDENTITY_DELETE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    withdraw_identity(db, user, identity)
    audit.record(
        db,
        action="identity.withdraw",
        actor_user_id=user.id,
        target_type="identity",
        target_id=identity.id,
        ip=_client_ip(request),
    )
    return {"ok": True}


@router.post("/verify", dependencies=[Depends(enforce_csrf)])
def verify(
    payload: dict[str, str],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, object]:
    """Verify that the person in front of the camera is the enrolled owner.

    Unenrolled people are never identified - the response only reports
    whether the owner's own template matched.
    """
    image = (payload or {}).get("image", "")
    if not image:
        raise HTTPException(status_code=422, detail="an image is required")
    try:
        result = verify_owner(db, user, image)
    except EnrollmentRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BiometricsUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except BiometricsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit.record(
        db,
        action="identity.verify",
        actor_user_id=user.id,
        target_type="identity",
        target_id="self",
        outcome="success" if result.get("matched") else "no_match",
        ip=_client_ip(request),
    )
    return result


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
