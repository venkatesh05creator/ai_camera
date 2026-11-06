"""Small shared runtime state (purposefully minimal and resettable)."""

from __future__ import annotations

from typing import Any


def reset_panic() -> None:
    PANIC["active"] = False
    PANIC["until"] = None
    PANIC["reason"] = None


PANIC: dict[str, Any] = {"active": False, "until": None, "reason": None}
