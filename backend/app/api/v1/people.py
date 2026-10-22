"""People Directory and Consent Management router."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...ai.verifier import FaceVerifier
from ...core.database import get_db
from ...models.entities import ConsentRecord, FaceTemplate, Person, User
from ...schemas.schemas import ConsentGrant, ConsentOut, PersonCreate, PersonOut, PersonUpdate
from ...services.audit_service import log_action
from ...services.consent_service import (
    ConsentError,
    grant_consent,
    save_biometric_template,
    withdraw_consent,
)
from ...core.security import PERM_PEOPLE_WRITE, has_permission
from .auth import get_current_user

router = APIRouter(prefix="/people", tags=["people"])
verifier = FaceVerifier(model_name="facenet")


def _person_to_out(person: Person, db: Session) -> PersonOut:
    now = datetime.now(timezone.utc)
    active_consent = db.scalars(
        select(ConsentRecord).where(
            ConsentRecord.person_id == person.id,
            ConsentRecord.withdrawn_at.is_(None),
            (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
        )
    ).first()

    templates_count = db.scalar(
        select(func.count(FaceTemplate.id)).where(
            FaceTemplate.person_id == person.id,
            FaceTemplate.revoked_at.is_(None),
        )
    ) or 0

    return PersonOut(
        id=person.id,
        name=person.name,
        age=person.age,
        gender=person.gender,
        role_relationship=person.role_relationship,
        contact_details=person.contact_details,
        notes=person.notes,
        photo_object_key=person.photo_object_key,
        status=person.status,
        first_seen_at=person.first_seen_at,
        last_seen_at=person.last_seen_at,
        created_at=person.created_at,
        consent_active=bool(active_consent),
        templates_count=templates_count,
    )


@router.get("", response_model=List[PersonOut])
def list_people(
    q: Optional[str] = Query(None, description="Search by name"),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Person).order_by(Person.name)
    if q:
        stmt = stmt.where(Person.name.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Person.status == status)

    people = db.scalars(stmt).all()
    return [_person_to_out(p, db) for p in people]


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(payload: PersonCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not has_permission(current_user.role, PERM_PEOPLE_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    person = Person(
        name=payload.name,
        age=payload.age,
        gender=payload.gender,
        role_relationship=payload.role_relationship,
        contact_details=payload.contact_details,
        notes=payload.notes,
        photo_object_key=payload.photo_base64[:100] if payload.photo_base64 else None,
        status="enrolled",
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    # Automatically grant baseline consent if created by admin
    grant_consent(db, person.id, recorded_by_user_id=current_user.id)

    log_action(db, action="person.create", resource_type="person", actor_user_id=current_user.id, resource_id=person.id, details={"name": person.name})
    return _person_to_out(person, db)


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return _person_to_out(person, db)


@router.put("/{person_id}", response_model=PersonOut)
def update_person(person_id: str, payload: PersonUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    if payload.name is not None:
        person.name = payload.name
    if payload.age is not None:
        person.age = payload.age
    if payload.gender is not None:
        person.gender = payload.gender
    if payload.role_relationship is not None:
        person.role_relationship = payload.role_relationship
    if payload.contact_details is not None:
        person.contact_details = payload.contact_details
    if payload.notes is not None:
        person.notes = payload.notes
    if payload.status is not None:
        person.status = payload.status

    db.commit()
    db.refresh(person)
    log_action(db, action="person.update", resource_type="person", actor_user_id=current_user.id, resource_id=person.id)
    return _person_to_out(person, db)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    # Withdraw consent and purge templates first
    withdraw_consent(db, person_id)
    db.delete(person)
    db.commit()
    log_action(db, action="person.delete", resource_type="person", actor_user_id=current_user.id, resource_id=person_id)


@router.post("/{person_id}/consent", response_model=ConsentOut)
def record_consent(person_id: str, payload: ConsentGrant, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not payload.confirm_explicit_consent:
        raise HTTPException(status_code=422, detail="Explicit consent agreement is required to store biometrics.")

    try:
        consent = grant_consent(
            db,
            person_id,
            recorded_by_user_id=current_user.id,
            consent_scope=payload.consent_scope,
            notice_version=payload.notice_version,
        )
        log_action(db, action="consent.grant", resource_type="consent", actor_user_id=current_user.id, resource_id=consent.id, details={"person_id": person_id})
        return consent
    except ConsentError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/{person_id}/withdraw")
def revoke_consent(person_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        withdraw_consent(db, person_id)
        log_action(db, action="consent.withdraw", resource_type="person", actor_user_id=current_user.id, resource_id=person_id)
        return {"status": "withdrawn", "detail": "Biometric templates deleted and consent revoked"}
    except ConsentError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/{person_id}/enroll")
def enroll_face_image(person_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Enroll a face image for a consented person. Decodes base64, extracts embedding, encrypts, and saves."""
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    image_b64 = payload.get("image_base64", "")
    if not image_b64:
        raise HTTPException(status_code=422, detail="image_base64 field is required")

    if "," in image_b64:
        image_b64 = image_b64.split(",")[1]

    try:
        img_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
    except Exception as err:
        raise HTTPException(status_code=422, detail=f"Invalid image format: {err}")

    # Detect face
    faces = verifier.engine.detect_faces(img)
    if not faces:
        raise HTTPException(status_code=422, detail="No face detected in the uploaded image")

    faces.sort(key=lambda b: b[2] * b[3], reverse=True)
    x, y, w, h = faces[0]
    face_roi = img[y : y + h, x : x + w]

    emb = verifier.extract_embedding_from_roi(face_roi)
    if emb is None:
        raise HTTPException(status_code=500, detail="Failed to extract embedding from face")

    try:
        template = save_biometric_template(db, person_id, emb.tolist(), model_version="facenet")
        # Also sync with JSON datastore for backward compatibility with live scripts
        verifier.engine.enroll_embedding(person.name, emb)

        log_action(db, action="biometrics.enroll", resource_type="template", actor_user_id=current_user.id, resource_id=template.id, details={"person_id": person_id})
        return {
            "status": "success",
            "template_id": template.id,
            "embedding_dim": template.embedding_dim,
            "person_name": person.name,
        }
    except ConsentError as err:
        raise HTTPException(status_code=403, detail=str(err))
