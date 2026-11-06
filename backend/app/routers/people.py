"""Consented people: consent enrolment, face templates, withdrawal.

Templates are never returned — public views carry metadata only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi import Path as ApiPath

from ..config import Settings
from ..dependencies import DbDep, require_owner, require_user
from ..models.session import Session as SessionRow
from ..models.user import User
from ..schemas import EnrolIn, PersonIn
from ..services import audit_service, people_service
from ..services.people_service import PeopleError

router = APIRouter(prefix="/api/people", tags=["people"])


@router.post("", status_code=201)
async def create(
    body: PersonIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    person = await people_service.create_person(
        db, name=body.name, consent_text=body.consent_text)
    await audit_service.record(
        db, "biometric.consent", actor_user_id=pair[0].id,
        target=f"person#{person.id}", detail={"name": person.name})
    await db.commit()
    return people_service.to_public(person, None)


@router.post("/{person_id}/enrol")
async def enrol(
    person_id: Annotated[int, ApiPath(ge=1)],
    body: EnrolIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    settings: Settings = request.app.state.settings
    result = await people_service.enrol(
        db, settings, person_id, body.images)
    await audit_service.record(
        db, "biometric.enrol", actor_user_id=pair[0].id,
        target=f"person#{person_id}",
        detail={"samples": result["samples"], "quality": result["quality"]})
    await db.commit()
    return result


@router.get("")
async def listing(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
) -> dict:
    from sqlalchemy import select

    from ..models.people import FaceTemplate

    templates = {t.person_id: t for t in
                 (await db.execute(select(FaceTemplate))).scalars().all()}
    people = [people_service.to_public(p, templates.get(p.id))
              for p in await people_service.list_people(db)]
    await db.commit()
    return {"people": people, "count": len(people)}


@router.get("/{person_id}/last-seen")
async def last_seen(
    person_id: Annotated[int, ApiPath(ge=1)],
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
) -> dict:
    """Latest events where this enrolled person was seen (decrypted)."""
    from sqlalchemy import select

    from ..models.cameras import CameraEvent
    from ..models.people import Person
    from ..services import camera_service  # noqa: F401 (kept for symmetry)

    person = await db.get(Person, person_id)
    if person is None:
        raise PeopleError("not_found", "person not found", 404)
    settings: Settings = request.app.state.settings
    rows = (await db.execute(
        select(CameraEvent)
        .where(CameraEvent.labels_encrypted.is_not(None))
        .order_by(CameraEvent.ts.desc()).limit(100))).scalars().all()
    seen = []
    for row in rows:
        labels = await people_service.decrypt_labels(
            settings, row.labels_encrypted)
        if any(k.get("person_id") == person_id for k in labels.get("known", [])):
            seen.append({"ts": row.ts.isoformat(), "camera_id": row.camera_id,
                         "kind": row.kind, "person_count": row.person_count})
            if len(seen) >= 20:
                break
    await db.commit()
    return {"person_id": person_id, "name": person.name, "seen": seen}


@router.delete("/{person_id}")
async def withdraw(
    person_id: Annotated[int, ApiPath(ge=1)],
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    db: DbDep,
) -> dict:
    if not await people_service.withdraw(db, person_id):
        raise PeopleError("not_found", "person not found", 404)
    await audit_service.record(
        db, "biometric.withdraw", actor_user_id=pair[0].id,
        target=f"person#{person_id}")
    await db.commit()
    return {"ok": True, "id": person_id,
            "note": "person and face template permanently deleted"}
