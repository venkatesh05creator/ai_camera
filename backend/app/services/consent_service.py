"""Consent lifecycle service: ensures consent-based biometrics and deletion upon withdrawal."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import encrypt_string
from ..models.entities import ConsentRecord, FaceTemplate, Person


class ConsentError(Exception):
    pass


def grant_consent(
    db: Session,
    person_id: str,
    recorded_by_user_id: str,
    consent_scope: str = "face_verification",
    notice_version: str = "1.0",
) -> ConsentRecord:
    """Record explicit consent for a person."""
    person = db.get(Person, person_id)
    if not person:
        raise ConsentError(f"Person {person_id} not found")

    record = ConsentRecord(
        person_id=person_id,
        consent_scope=consent_scope,
        notice_version=notice_version,
        granted_at=datetime.now(timezone.utc),
        recorded_by_user_id=recorded_by_user_id,
    )
    db.add(record)
    person.status = "enrolled"
    db.commit()
    db.refresh(record)
    return record


def withdraw_consent(db: Session, person_id: str) -> None:
    """Withdraw consent: instantly revokes and purges biometric face templates."""
    person = db.get(Person, person_id)
    if not person:
        raise ConsentError(f"Person {person_id} not found")

    now = datetime.now(timezone.utc)

    # 1. Mark consent records withdrawn
    stmt = select(ConsentRecord).where(ConsentRecord.person_id == person_id, ConsentRecord.withdrawn_at.is_(None))
    for consent in db.scalars(stmt).all():
        consent.withdrawn_at = now

    # 2. Revoke and purge all face templates for this person
    template_stmt = select(FaceTemplate).where(FaceTemplate.person_id == person_id)
    for template in db.scalars(template_stmt).all():
        template.revoked_at = now
        # Overwrite biometric data with empty bytes to prevent retention
        template.template_encrypted = b""

    person.status = "withdrawn"
    db.commit()


def save_biometric_template(
    db: Session,
    person_id: str,
    embedding: list[float],
    model_version: str = "facenet",
) -> FaceTemplate:
    """Save an AES-256-GCM encrypted biometric template for an enrolled person."""
    person = db.get(Person, person_id)
    if not person:
        raise ConsentError("Person not found")

    # Check for active consent
    now = datetime.now(timezone.utc)
    consent_stmt = select(ConsentRecord).where(
        ConsentRecord.person_id == person_id,
        ConsentRecord.withdrawn_at.is_(None),
        (ConsentRecord.expires_at.is_(None) | (ConsentRecord.expires_at > now)),
    )
    active_consent = db.scalars(consent_stmt).first()
    if not active_consent:
        raise ConsentError("Cannot store biometric template: person has no active consent record")

    payload_json = json.dumps(embedding)
    encrypted_blob = encrypt_string(payload_json, aad=b"biometric-template")

    template = FaceTemplate(
        person_id=person_id,
        template_encrypted=encrypted_blob,
        model_version=model_version,
        embedding_dim=len(embedding),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template
