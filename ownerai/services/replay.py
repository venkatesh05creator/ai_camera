"""Per-turn replay / audit log of every assistant turn (Phase 3B rank #4).

Records the question, resolved intent, tools called, evidence event IDs used,
and the answer so that every JARVIS response can be traced back to its source.

Ships behind the ``REPLAY_LOG`` feature flag.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import session_scope
from ..features import is_enabled
from ..models import AssistantTurn, User
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)


class ReplayLog:
    """Append-only log of assistant turns.

    Safe to call when the flag is disabled: every method is a no-op.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _enabled(self) -> bool:
        return is_enabled("REPLAY_LOG")

    def record(
        self,
        *,
        owner_id: int,
        user_message: str,
        intent: str,
        tools_called: list[dict[str, Any]],
        evidence_event_ids: list[int],
        answer: str,
        conversation_id: Optional[int] = None,
    ) -> Optional[int]:
        """Append a turn record and return its id (None if flag disabled)."""
        if not self._enabled():
            return None
        with session_scope(self.settings) as db:
            turn = AssistantTurn(
                conversation_id=conversation_id,
                owner_id=owner_id,
                user_message=user_message,
                intent=intent,
                tools_called_json=json.dumps(tools_called),
                evidence_event_ids_json=json.dumps(evidence_event_ids),
                answer=answer,
            )
            db.add(turn)
            db.flush()
            turn_id = turn.id
        logger.debug("replay turn recorded", extra={"turn_id": turn_id, "owner_id": owner_id})
        return turn_id

    def list_turns(
        self,
        owner_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return recent turns for an owner, newest first."""
        if not self._enabled():
            return []
        with session_scope(self.settings) as db:
            rows = (
                db.query(AssistantTurn)
                .filter_by(owner_id=owner_id)
                .order_by(AssistantTurn.created_at.desc())
                .limit(max(1, min(limit, 200)))
                .offset(max(0, offset))
                .all()
            )
        return [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "user_message": r.user_message,
                "intent": r.intent,
                "tools_called": json.loads(r.tools_called_json or "[]"),
                "evidence_event_ids": json.loads(r.evidence_event_ids_json or "[]"),
                "answer": r.answer,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
