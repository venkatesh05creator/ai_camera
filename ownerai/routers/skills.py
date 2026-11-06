"""Skills format endpoints (Phase O-5).

Tools are declared in one validated manifest file and loaded through a
validated interface.  Skills are NOT self-installed from the internet.
Ships behind the ``SKILLS_FORMAT`` feature flag.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from ..features import is_enabled
from ..services.skills import SkillError, SkillsRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills format"])

# A single registry instance for the application.  Handlers are registered
# in code (never auto-installed from the internet); skills are loaded from a
# validated manifest.
_registry = SkillsRegistry()


def _require_skills() -> None:
    if not is_enabled("SKILLS_FORMAT"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SKILLS_FORMAT feature is not enabled "
            "(set OWNERAI_FEATURE_SKILLS_FORMAT=1)",
        )


@router.get("")
def list_skills() -> dict[str, Any]:
    """List loaded skills (their declarations, not handlers)."""
    _require_skills()
    skills = _registry.list_skills()
    return {
        "feature": "SKILLS_FORMAT",
        "skills": {
            name: {
                "description": skill.description,
                "mutating": skill.mutating,
                "input_schema": skill.input_schema,
                "handler": skill.handler,
            }
            for name, skill in skills.items()
        },
    }


@router.post("/manifest")
def load_manifest(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Load a skill manifest file.

    Body: ``{"path": "skills/manifest.json"}``.  The manifest declares skills
    whose handlers must already be registered in code; skills are never
    self-installed from the internet.
    """
    _require_skills()
    path = str(payload.get("path", "")).strip()
    if not path:
        raise HTTPException(status_code=422, detail="path is required")
    try:
        loaded = _registry.load_manifest(path)
    except SkillError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "feature": "SKILLS_FORMAT",
        "loaded": {name: skill.description for name, skill in loaded.items()},
    }
