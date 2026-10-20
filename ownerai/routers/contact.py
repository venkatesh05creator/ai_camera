"""Public contact form endpoint."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import enforce_csrf
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..schemas import ContactRequest
from ..services.contact import ContactRejected, store_submission, validate_submission
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["contact"])

#: Time the form was rendered; used as a cheap bot trap.
_FORM_RENDERED_AT = time.monotonic()


def mark_form_rendered() -> None:
    """Remember when the contact form was served."""
    global _FORM_RENDERED_AT
    _FORM_RENDERED_AT = time.monotonic()


@router.post("/contact", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(enforce_csrf)])
def submit_contact(
    payload: ContactRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Accept a contact request.

    The response is identical for accepted and rejected submissions so that
    the endpoint cannot be used to probe for open relays.
    """
    from ..middleware import client_ip

    settings = get_settings()
    ip = client_ip(request)

    try:
        check_rate_limit(
            db,
            "contact",
            ip,
            settings.contact_rate_limit,
            settings.contact_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many messages, please try again later",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    elapsed = time.monotonic() - _FORM_RENDERED_AT
    try:
        email, subject, message = validate_submission(
            email=payload.email,
            subject=payload.subject,
            message=payload.message,
            honeypot=payload.website,
            elapsed_seconds=elapsed,
        )
    except ContactRejected as exc:
        logger.info("contact submission rejected", extra={"reason": str(exc)})
        # Answer as if it was accepted - a honeypot hit should not tell the
        # sender that the form detected it.
        return {"message": "Thank you - your message has been received."}

    try:
        store_submission(db, email=email, subject=subject, message=message, ip=ip)
    except Exception:  # pragma: no cover - storage failure
        logger.exception("contact message could not be stored")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the message could not be stored, please try again later",
        ) from None

    logger.info("contact message stored", extra={"subject_length": len(subject)})
    return {"message": "Thank you - your message has been received."}
