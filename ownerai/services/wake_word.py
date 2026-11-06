"""Local wake word + voice command integration (Phase 3B rank #3).

The actual wake word detection (openWakeWord / Porcupine) and
speech-to-text happen client-side on the owner's device.  This service
tracks wake word sessions and provides the server-side integration point
for voice commands.  No audio is recorded or stored by the server.
Ships behind the ``WAKE_WORD`` feature flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..db import session_scope
from ..features import is_enabled
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class WakeWordSession:
    """A wake word session (client-side detection acknowledged by server)."""

    session_id: str
    device_id: str
    woke_at: datetime
    expires_at: datetime
    commands: list[dict[str, Any]] = field(default_factory=list)

    def is_active(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


class WakeWordService:
    """Tracks wake word sessions and voice command state."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._sessions: dict[str, WakeWordSession] = {}

    def _enabled(self) -> bool:
        return is_enabled("WAKE_WORD")

    def register_wake_word(
        self,
        session_id: str,
        device_id: str,
        ttl_seconds: int = 30,
    ) -> Optional[WakeWordSession]:
        """Acknowledge a client-side wake word detection.

        Returns the session or None if the flag is disabled.
        """
        if not self._enabled():
            return None
        now = datetime.now(timezone.utc)
        session = WakeWordSession(
            session_id=session_id,
            device_id=device_id,
            woke_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._sessions[session_id] = session
        logger.info("wake word registered", extra={"session": session_id, "device": device_id})
        return session

    def get_session(self, session_id: str) -> Optional[WakeWordSession]:
        """Return an active wake word session, or None."""
        if not self._enabled():
            return None
        session = self._sessions.get(session_id)
        if session is None or not session.is_active():
            return None
        return session

    def record_command(
        self,
        session_id: str,
        command: str,
        intent: str,
        response: str,
    ) -> bool:
        """Record a voice command within an active session."""
        if not self._enabled():
            return False
        session = self.get_session(session_id)
        if session is None:
            return False
        session.commands.append(
            {
                "command": command,
                "intent": intent,
                "response": response,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return True

    def list_active_sessions(self) -> list[dict[str, Any]]:
        """List all active wake word sessions."""
        if not self._enabled():
            return []
        now = datetime.now(timezone.utc)
        return [
            {
                "session_id": s.session_id,
                "device_id": s.device_id,
                "woke_at": s.woke_at.isoformat(),
                "expires_at": s.expires_at.isoformat(),
                "command_count": len(s.commands),
            }
            for s in self._sessions.values()
            if s.is_active()
        ]


_wake_word = WakeWordService()
