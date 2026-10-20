"""Permission filtered search across the dashboard.

Every query is executed through the ORM with bound parameters and is scoped
to the resources the caller is allowed to see.  Search never triggers AI
calls, file access or free-form SQL.
"""

from __future__ import annotations

import logging
from typing import Any, List

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..crypto import mask_email
from ..models import CameraEvent, Conversation, Device, EnrolledIdentity, User
from ..rbac import ADMIN_USERS, has_permission
from ..schemas import SearchHit

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 120
MAX_RESULTS_PER_TYPE = 10

HELP_DOCS: List[dict] = [
    {
        "title": "Getting started",
        "url": "/docs#getting-started",
        "snippet": "Register your cameras, enrol your own face and start the assistant.",
        "keywords": "start onboarding register camera setup",
    },
    {
        "title": "Camera privacy",
        "url": "/docs#privacy",
        "snippet": "What is stored, for how long, and how to delete it.",
        "keywords": "privacy retention delete data gdpr",
    },
    {
        "title": "Enrolling a face template",
        "url": "/docs#enrolment",
        "snippet": "How biometric enrolment works, how to withdraw consent.",
        "keywords": "biometric enrol face template consent withdraw",
    },
    {
        "title": "Multi-factor authentication",
        "url": "/docs#mfa",
        "snippet": "Protect your account with a TOTP authenticator app.",
        "keywords": "mfa totp two factor authenticator",
    },
    {
        "title": "Device tokens",
        "url": "/docs#device-tokens",
        "snippet": "Authenticate phones and wearables that push camera events.",
        "keywords": "device token android wearable ingest",
    },
    {
        "title": "Assistant safety rules",
        "url": "/docs#assistant",
        "snippet": "What the AI assistant may and may not do.",
        "keywords": "assistant ai prompt injection rules tools",
    },
]


def _escape_like(term: str) -> str:
    """Escape the wildcards of a LIKE pattern."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(
    db: Session,
    user: User,
    query: str,
    *,
    limit: int = MAX_RESULTS_PER_TYPE,
) -> tuple[int, List[SearchHit]]:
    """Search the caller's own resources plus the public help documentation."""
    query = (query or "").strip()
    if not query:
        return 0, []
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
    pattern = f"%{_escape_like(query)}%"

    hits: List[SearchHit] = []

    devices = db.scalars(
        select(Device)
        .where(Device.owner_id == user.id)
        .where(or_(Device.name.ilike(pattern, escape="\\"), Device.location_label.ilike(pattern, escape="\\")))
        .limit(limit)
    ).all()
    for device in devices:
        hits.append(
            SearchHit(
                type="device",
                id=device.id,
                title=device.name,
                snippet=f"{device.device_type} - {device.status}",
                url=f"/dashboard#device-{device.id}",
            )
        )

    identities = db.scalars(
        select(EnrolledIdentity)
        .where(EnrolledIdentity.owner_id == user.id)
        .where(EnrolledIdentity.label.ilike(pattern, escape="\\"))
        .limit(limit)
    ).all()
    for identity in identities:
        hits.append(
            SearchHit(
                type="identity",
                id=identity.id,
                title=identity.label,
                snippet="Enrolled biometric template",
                url=f"/dashboard#identity-{identity.id}",
            )
        )

    events = db.scalars(
        select(CameraEvent)
        .where(CameraEvent.owner_id == user.id)
        .where(CameraEvent.summary.ilike(pattern, escape="\\"))
        .order_by(CameraEvent.occurred_at.desc())
        .limit(limit)
    ).all()
    for event in events:
        hits.append(
            SearchHit(
                type="event",
                id=event.id,
                title=event.kind,
                snippet=event.summary[:120],
                url=f"/dashboard#event-{event.id}",
            )
        )

    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.owner_id == user.id)
        .where(Conversation.title.ilike(pattern, escape="\\"))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    ).all()
    for conversation in conversations:
        hits.append(
            SearchHit(
                type="conversation",
                id=conversation.id,
                title=conversation.title,
                snippet="AI conversation",
                url=f"/dashboard#conversation-{conversation.id}",
            )
        )

    if has_permission(user.role, ADMIN_USERS):
        users = db.scalars(
            select(User)
            .where(or_(User.email.ilike(pattern, escape="\\"), User.display_name.ilike(pattern, escape="\\")))
            .limit(limit)
        ).all()
        for found in users:
            hits.append(
                SearchHit(
                    type="user",
                    id=found.id,
                    title=found.display_name or mask_email(found.email),
                    snippet=f"role={found.role}",
                    url="/admin#users",
                )
            )

    lowered = query.lower()
    for doc in HELP_DOCS:
        if lowered in doc["keywords"] or lowered in doc["title"].lower() or lowered in doc["snippet"].lower():
            hits.append(
                SearchHit(
                    type="help",
                    id=0,
                    title=doc["title"],
                    snippet=doc["snippet"],
                    url=doc["url"],
                )
            )

    return len(hits), hits


def search_public_docs(query: str) -> List[SearchHit]:
    """Search the public documentation (used for anonymous visitors)."""
    query = (query or "").strip()
    if not query:
        return []
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
    lowered = query.lower()
    hits: List[SearchHit] = []
    for doc in HELP_DOCS:
        haystack = f"{doc['title']} {doc['snippet']} {doc['keywords']}".lower()
        if lowered in haystack:
            hits.append(
                SearchHit(
                    type="help",
                    id=0,
                    title=doc["title"],
                    snippet=doc["snippet"],
                    url=doc["url"],
                )
            )
    return hits


def count_resources(db: Session, user: User) -> dict[str, Any]:
    """Return the counters shown on the dashboard."""
    devices = db.scalar(select(func.count(Device.id)).where(Device.owner_id == user.id))
    events = db.scalar(select(func.count(CameraEvent.id)).where(CameraEvent.owner_id == user.id))
    identities = db.scalar(
        select(func.count(EnrolledIdentity.id)).where(
            EnrolledIdentity.owner_id == user.id, EnrolledIdentity.withdrawn_at.is_(None)
        )
    )
    conversations = db.scalar(select(func.count(Conversation.id)).where(Conversation.owner_id == user.id))
    return {
        "devices": int(devices or 0),
        "events": int(events or 0),
        "identities": int(identities or 0),
        "conversations": int(conversations or 0),
    }
