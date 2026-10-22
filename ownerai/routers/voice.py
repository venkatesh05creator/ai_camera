"""Voice command endpoints.

The browser does the speech recognition and the speech synthesis, the server
turns the transcript into a deterministic answer (or hands a free-form
question to the assistant).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import Conversation, Message, User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import CHAT_WRITE, has_permission
from ..schemas import StrictModel
from ..services import audit
from ..services.ai import AIError, AIQuotaExceeded, generate_reply
from ..services.voice import build_command, command_to_payload, help_text
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceCommandRequest(StrictModel):
    """A spoken (or typed) command."""

    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="en-US", max_length=16)
    conversation_id: Optional[int] = Field(default=None, ge=1)
    speak: bool = True


@router.get("/commands", response_model=List[str])
def list_commands(user: User = Depends(authenticated_user)) -> List[str]:
    """Return the phrases the deterministic parser understands."""
    from ..services.voice import _KEYWORD_INTENTS

    seen = []
    for phrase, _intent in _KEYWORD_INTENTS:
        if phrase not in seen:
            seen.append(phrase)
    return seen


@router.get("/help")
def voice_help(user: User = Depends(authenticated_user)) -> Dict[str, str]:
    """A short, speakable description of the available commands."""
    return {"help": help_text()}


@router.post("/command")
def run_command(
    payload: VoiceCommandRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
    _: None = Depends(enforce_csrf),
) -> Dict[str, Any]:
    """Interpret one voice command and return the text to display and to speak."""
    if not has_permission(user.role, CHAT_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "voice",
            f"user:{user.id}",
            settings.ai_rate_limit,
            settings.ai_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many voice commands, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    command = build_command(db, user, payload.text, language=payload.language)

    if not command.use_assistant:
        audit.record(
            db,
            action="voice.command",
            actor_user_id=user.id,
            target_type="voice_intent",
            target_id=command.intent,
            ip=_client_ip(request),
        )
        return command_to_payload(command)

    # Free-form question: hand it to the assistant.
    conversation: Optional[Conversation] = None
    if payload.conversation_id is not None:
        conversation = db.get(Conversation, payload.conversation_id)
        if conversation is None or conversation.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    else:
        conversation = Conversation(owner_id=user.id, title=payload.text.strip()[:80] or "Voice conversation")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    db.add(Message(conversation_id=conversation.id, role="user", content=payload.text[:4000]))
    db.commit()

    try:
        response = generate_reply(db, user, payload.text, conversation=conversation, settings=settings)
    except AIQuotaExceeded as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AIError as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="the assistant is unavailable") from exc

    answer = response.text
    assistant_message = Message(
        conversation_id=conversation.id, role="assistant", content=answer, tokens=response.tokens
    )
    db.add(assistant_message)
    conversation.token_count += response.tokens
    db.commit()
    db.refresh(assistant_message)

    audit.record(
        db,
        action="voice.assistant",
        actor_user_id=user.id,
        target_type="conversation",
        target_id=conversation.id,
        ip=_client_ip(request),
        detail={"provider": response.provider},
    )

    command.answer = answer
    command.speak = answer
    payload_out = command_to_payload(command, conversation_id=conversation.id)
    payload_out["message_id"] = assistant_message.id
    payload_out["tokens_used"] = response.tokens
    payload_out["provider"] = response.provider
    return payload_out


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
