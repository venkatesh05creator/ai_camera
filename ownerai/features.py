"""Feature flags for Aegis AI innovation features.

Every Phase 3 / Phase 3B innovation ships behind a feature flag so that the
owner can opt in consciously and the core security behaviour is never altered
by an unchecked default.

Flags are read from the environment (``OWNERAI_FEATURE_<NAME>``) with a
documented default.  ``OWNERAI_FEATURE_<NAME>=1/true`` enables, any other
value (or unset) uses the default.  All defaults are ``False`` (opt-in) so
that new capabilities never change behaviour for existing deployments unless
the owner explicitly enables them.

Example::

    # .env
    OWNERAI_FEATURE_CAMERA_HEALTH=1
    OWNERAI_FEATURE_LEARNED_BASELINE=0
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Final


def _env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean feature flag from ``OWNERAI_FEATURE_<name>``."""
    raw = os.environ.get(f"OWNERAI_FEATURE_{name}")
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class FeatureFlag:
    """A single feature flag."""

    name: str
    description: str
    default: bool = False
    #: When True, the flag can only be flipped by an owner with admin rights.
    owner_only: bool = True


#: All innovation flags.  Defaults are opt-in (False) so existing
#: deployments keep their current behaviour.
FLAGS: Final[Dict[str, FeatureFlag]] = {
    # Phase 3B - GitHub research transplants
    "CAMERA_HEALTH": FeatureFlag(
        "CAMERA_HEALTH",
        "Camera tamper & health detection (lens covered, blur, low light, frozen stream).",
        default=False,
    ),
    "LEARNED_BASELINE": FeatureFlag(
        "LEARNED_BASELINE",
        "Learned 'normal' per-camera / time-of-day baseline with deviation alerts.",
        default=False,
    ),
    "WAKE_WORD": FeatureFlag(
        "WAKE_WORD",
        "Local wake word + speech-to-text + streaming TTS (offline-first voice).",
        default=False,
    ),
    "REPLAY_LOG": FeatureFlag(
        "REPLAY_LOG",
        "Per-turn replay/audit log of every assistant turn (question, intent, tools, evidence, answer).",
        default=False,
    ),
    "DOCTOR": FeatureFlag(
        "DOCTOR",
        "Startup health probes and benchmark commands (camera, model, DB, disk).",
        default=False,
    ),
    "MCP_RUNTIME": FeatureFlag(
        "MCP_RUNTIME",
        "Pluggable Model Context Protocol tool runtime behind a validated interface.",
        default=False,
    ),
    # Phase 3 - innovation
    "EVIDENCE_PANEL": FeatureFlag(
        "EVIDENCE_PANEL",
        "Every JARVIS answer links to the exact snapshot/event IDs, detector output and confidence behind it.",
        default=False,
    ),
    "ALERT_RULES": FeatureFlag(
        "ALERT_RULES",
        "Natural-language alert rules parsed into validated rules, confirmed by the owner before activation.",
        default=False,
    ),
    "PRIVACY_ZONES": FeatureFlag(
        "PRIVACY_ZONES",
        "Owner-drawn privacy zones that are never analysed or stored; non-enrolled faces blurred in saved clips.",
        default=False,
    ),
    "DIGEST": FeatureFlag(
        "DIGEST",
        "Daily/weekly narrative digest built only from stored events.",
        default=False,
    ),
    "GUEST_ACCESS": FeatureFlag(
        "GUEST_ACCESS",
        "Time-boxed guest enrolment that expires automatically.",
        default=False,
    ),
    "OFFLINE_FIRST": FeatureFlag(
        "OFFLINE_FIRST",
        "Local vision plus offline AI provider so the app works without internet.",
        default=False,
    ),
    "WORLD_MONITOR": FeatureFlag(
        "WORLD_MONITOR",
        "Lawful public-data layers (aircraft, earthquakes, fires, cyber) as "
        "read-only JARVIS tools; no person tracking.",
        default=False,
    ),
    "EVAL_HARNESS": FeatureFlag(
        "EVAL_HARNESS",
        "Offline evaluation harness measuring grounding accuracy and "
        "hallucinated detections in JARVIS turns.",
        default=False,
    ),
}


def is_enabled(feature: str) -> bool:
    """Return whether a feature flag is enabled.

    Unknown features are treated as disabled so that a misspelled name never
    silently enables something.
    """
    flag = FLAGS.get(feature)
    if flag is None:
        return False
    return _env_flag(feature, flag.default)


def enabled_features() -> Dict[str, bool]:
    """Return every flag and its current state (useful for /health / diagnostics)."""
    return {name: is_enabled(name) for name in FLAGS}


def require(feature: str) -> None:
    """Decorator/helper that raises when a feature is not enabled.

    Intended to guard innovation endpoints so that disabled features return a
    clear 403/404 rather than silently failing.
    """
    if not is_enabled(feature):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403,
            detail=f"feature '{feature}' is not enabled (set OWNERAI_FEATURE_{feature}=1)",
        )
