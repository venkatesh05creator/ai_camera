"""MCP tool runtime endpoints (Phase 3B rank #7).

Ships behind the ``MCP_RUNTIME`` feature flag.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user
from ..features import is_enabled
from ..models import User
from ..services.mcp import MCPError, MCPRuntime
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp runtime"])

_mcp = MCPRuntime()


def _require_mcp() -> None:
    if not is_enabled("MCP_RUNTIME"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP_RUNTIME feature is not enabled (set OWNERAI_FEATURE_MCP_RUNTIME=1)",
        )


@router.get("/tools")
def list_mcp_tools(
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """List all registered MCP tools."""
    _require_mcp()
    return {"feature": "MCP_RUNTIME", "tools": _mcp.list_tools()}


@router.post("/tools/{tool_name}/call")
def call_mcp_tool(
    tool_name: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict:
    """Call an MCP tool.

    Body: ``{"arguments": {...}, "confirmed": true}``
    """
    _require_mcp()
    arguments = (payload or {}).get("arguments") or {}
    confirmed = bool((payload or {}).get("confirmed", False))
    if not isinstance(arguments, dict):
        raise HTTPException(status_code=422, detail="arguments must be an object")
    try:
        return _mcp.call(tool_name, arguments, confirmed=confirmed)
    except MCPError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
