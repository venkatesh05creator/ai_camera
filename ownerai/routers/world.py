"""World Monitor API (Phase W).

Lawful public-data layers exposed to the owner as read-only JARVIS tool
results and via these endpoints.  All third-party calls go through the
backend proxy (ownerai/services/world.py) with caching and rate limits.
API keys never reach the browser.

Ships behind the ``WORLD_MONITOR`` feature flag.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import User
from ..services.world import WorldError, available_sources, fetch_source
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/world", tags=["world monitor"])

#: Sources the UI may offer as map layers (subset of the full registry that are
#: safe to render without per-source keys).  Fires requires an API key and is
#: gated separately.
UI_LAYER_SOURCES = ("aircraft", "earthquakes", "cyber")


def _require_world_monitor() -> None:
    if not is_enabled("WORLD_MONITOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WORLD_MONITOR feature is not enabled "
            "(set OWNERAI_FEATURE_WORLD_MONITOR=1)",
        )


@router.get("/sources")
def list_sources() -> dict[str, Any]:
    """Return configured sources with availability and attribution."""
    _require_world_monitor()
    settings = get_settings()
    return {
        "feature": "WORLD_MONITOR",
        "sources": available_sources(settings),
    }


@router.get("/{source}")
def get_source(
    source: str,
    refresh: bool = Query(default=False, description="bypass cache and refetch"),
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Fetch one lawful public-data layer.

    Results are cached server-side; set ``?refresh=1`` to bypass the cache
    (subject to the source rate limit).
    """
    _require_world_monitor()
    try:
        return fetch_source(source, settings=get_settings(), force_refresh=refresh)
    except WorldError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get("/layers")
def list_layers() -> dict[str, Any]:
    """Return the map layers the UI may render (read-only, attributed)."""
    _require_world_monitor()
    settings = get_settings()
    return {
        "feature": "WORLD_MONITOR",
        "layers": [
            {
                "id": s["id"],
                "name": s["name"],
                "attribution": s["attribution"],
                "available": s["available"],
            }
            for s in available_sources(settings)
            if s["id"] in UI_LAYER_SOURCES
        ],
    }
