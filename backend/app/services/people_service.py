"""People service: consent, enrolment, identification, withdrawal.

Hard rules:
- no consent record -> enrolment impossible (server-side, not UI-only)
- identify() only ever matches against consented templates
- anything below threshold is "unknown" — a stranger is never named
- withdrawal hard-deletes the person + template (cascade), kept in the
  audit chain as "biometric.withdraw" for accountability
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.people import FaceTemplate, Person
from ..models.user import utcnow
from ..security.crypto import decrypt_text, encrypt_text
from ..vision.face import FaceEngineNotInstalled, get_engine, identify
from .memory_service import memory_key


class PeopleError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def _decode_jpeg(b64: str) -> bytes:
    text = b64.strip()
    if text.startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        return base64.b64decode(text, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise PeopleError("bad_image", "image is not valid base64 data",
                          422) from exc


def to_public(person: Person, template: FaceTemplate | None) -> dict:
    return {
        "id": person.id,
        "name": person.name,
        "consent_ts": person.consent_ts.isoformat(),
        "created_at": person.created_at.isoformat(),
        "has_template": template is not None,
        "samples_count": template.samples_count if template else 0,
        "quality": template.quality if template else None,
        # template bytes are NEVER part of the public view
    }


# ------------------------------------------------------------------ consent
async def create_person(session: AsyncSession, *,
                        name: str, consent_text: str) -> Person:
    name = " ".join(name.split())[:120]
    statement = " ".join(consent_text.split())[:2000]
    if not name:
        raise PeopleError("empty_name", "name cannot be empty", 422)
    if len(statement) < 20:
        raise PeopleError(
            "consent_required",
            "type the consent statement (min 20 characters) before enrolling",
            422)
    person = Person(
        name=name,
        consent_ts=utcnow(),
        consent_statement_hash=hashlib.sha256(
            statement.encode("utf-8")).hexdigest())
    session.add(person)
    await session.flush()
    return person


# --------------------------------------------------------------- enrolment
async def enrol(session: AsyncSession, settings: Settings,
                person_id: int, sample_jpegs: list[str]) -> dict:
    """Store the averaged embedding of the sample frames (encrypted)."""
    person = await session.get(Person, person_id)
    if person is None:
        raise PeopleError("not_found", "person not found", 404)
    minimum = settings.face_min_enrol_samples
    if len(sample_jpegs) < minimum:
        raise PeopleError(
            "too_few_samples",
            f"at least {minimum} face samples are required", 422)

    try:
        engine = get_engine(settings)
    except FaceEngineNotInstalled as exc:
        raise PeopleError("face_engine_missing", str(exc), 503) from exc

    import cv2

    embeddings, quality = [], []
    for raw in samples_to_bytes(sample_jpegs):
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                             cv2.IMREAD_COLOR)
        if frame is None:
            raise PeopleError("bad_image",
                              "a sample is not a decodable image", 422)
        faces = engine.read_faces(frame)
        usable = [f for f in faces if f.quality >= 0.3]
        if not usable:
            raise PeopleError(
                "no_face_in_sample",
                "one sample contains no detectable face "
                "(take a brighter, front-facing photo)", 422)
        best = max(usable, key=lambda f: f.quality)
        embeddings.append(best.embedding)
        quality.append(best.quality)

    template_vec = engine.average(embeddings)
    ciphertext = encrypt_text(
        memory_key(settings),
        json.dumps([round(float(v), 6) for v in template_vec]))

    existing = (await session.execute(
        select(FaceTemplate).where(FaceTemplate.person_id == person_id))
    ).scalar_one_or_none()
    if existing is None:
        session.add(FaceTemplate(
            person_id=person_id, embedding_encrypted=ciphertext,
            samples_count=len(embeddings),
            quality=round(sum(quality) / len(quality), 3)))
    else:
        existing.embedding_encrypted = ciphertext
        existing.samples_count = len(embeddings)
        existing.quality = round(sum(quality) / len(quality), 3)
        existing.updated_at = utcnow()
    await session.flush()
    return {"id": person.id, "samples": len(embeddings),
            "quality": round(sum(quality) / len(quality), 3)}


def samples_to_bytes(sample_jpegs: list[str]) -> list[bytes]:
    return [_decode_jpeg(s) for s in sample_jpegs]


# ------------------------------------------------------------- identification
async def load_templates(session: AsyncSession,
                         settings: Settings) -> list[tuple[int, np.ndarray]]:
    rows = (await session.execute(
        select(FaceTemplate, Person)
        .join(Person, FaceTemplate.person_id == Person.id))).all()
    templates = []
    for template, person in rows:
        if person.consent_ts is None:  # pragma: no cover - consent cannot lapse
            continue
        vec = np.array(json.loads(
            decrypt_text(memory_key(settings), template.embedding_encrypted)),
            dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            templates.append((person.id, vec / norm))
    return templates


async def identify_faces(session: AsyncSession, settings: Settings,
                         frame: np.ndarray) -> list[dict]:
    """Per detected face: enrolled person (name+score) or unknown."""
    try:
        engine = get_engine(settings)
    except FaceEngineNotInstalled:
        return []  # no engine -> no identification claims at all
    templates = await load_templates(session, settings)
    names = {row.id: row.name for row in
             (await session.execute(select(Person))).scalars().all()}
    results = []
    for face in engine.read_faces(frame):
        person_id, score = identify(face.embedding, templates,
                                    threshold=settings.face_match_threshold)
        if person_id is not None:
            results.append({"known": True, "person_id": person_id,
                            "name": names.get(person_id, "?"),
                            "score": round(score, 3)})
        else:
            results.append({"known": False, "person_id": None,
                            "score": round(score, 3)})
    return results


def labels_to_json(faces: list[dict]) -> str:
    known = [f for f in faces if f["known"]]
    unknown = sum(1 for f in faces if not f["known"])
    return json.dumps({"known": known, "unknown_faces": unknown})


# --------------------------------------------------------- list / withdraw
async def list_people(session: AsyncSession) -> list[Person]:
    return list((await session.execute(
        select(Person).order_by(Person.id.asc()))).scalars().all())


async def withdraw(session: AsyncSession, person_id: int) -> bool:
    """Hard-delete the person and their template (CASCADE)."""
    person = await session.get(Person, person_id)
    if person is None:
        return False
    await session.execute(
        delete(FaceTemplate).where(FaceTemplate.person_id == person_id))
    await session.execute(delete(Person).where(Person.id == person_id))
    await session.flush()
    return True


async def decrypt_labels(settings: Settings, encrypted: str | None) -> dict:
    if not encrypted:
        return {"known": [], "unknown_faces": 0, "has_labels": False}
    try:
        payload = json.loads(
            decrypt_text(memory_key(settings), encrypted))
        return {**payload, "has_labels": True}
    except Exception:
        return {"known": [], "unknown_faces": 0, "has_labels": False,
                "decrypt_error": True}
