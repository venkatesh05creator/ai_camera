"""Permission filtered search endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import optional_user
from ..models import User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import SEARCH_READ, has_permission
from ..schemas import SearchResponse
from ..services.search import search, search_public_docs
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search_endpoint(
    request: Request,
    q: str = Query(default="", min_length=0, max_length=120),
    db: Session = Depends(get_db),
    user: User = Depends(optional_user),
) -> SearchResponse:
    """Search the caller's own resources and the public documentation.

    Results are filtered with the same ownership rules as the corresponding
    pages, so a search can never reveal another account's data.  Anonymous
    visitors only see the public documentation.
    """
    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "search",
            f"user:{user.id}" if user else f"ip:{_client_ip(request)}",
            settings.search_rate_limit,
            settings.search_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many search requests",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    if user is None:
        hits = search_public_docs(q)
        return SearchResponse(query=q[:120], total=len(hits), hits=hits)

    if not has_permission(user.role, SEARCH_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    total, hits = search(db, user, q)
    return SearchResponse(query=q[:120], total=total, hits=hits)


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
