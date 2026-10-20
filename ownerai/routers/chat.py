"""AI assistant endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import authenticated_user, enforce_csrf
from ..models import Conversation, Message, User
from ..ratelimit import RateLimitExceeded, check_rate_limit
from ..rbac import CHAT_READ, CHAT_WRITE, has_permission
from ..schemas import ChatRequest, ChatResponse, ConversationOut, MessageOut
from ..services import audit
from ..services.ai import (
    AIError,
    AIQuotaExceeded,
    execute_tool,
    generate_reply,
    parse_tool_call,
)
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["assistant"])


@router.get("/conversations", response_model=List[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), user: User = Depends(authenticated_user)
) -> List[ConversationOut]:
    """List the conversations of the authenticated owner."""
    if not has_permission(user.role, CHAT_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.owner_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    ).all()
    return [ConversationOut.model_validate(conversation) for conversation in conversations]


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageOut])
def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> List[MessageOut]:
    """Return the messages of one of the owner's conversations."""
    conversation = _get_conversation(db, conversation_id, user)
    if not has_permission(user.role, CHAT_READ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id)
        .limit(200)
    ).all()
    return [MessageOut.model_validate(message) for message in messages]


@router.post("", response_model=ChatResponse, dependencies=[Depends(enforce_csrf)])
def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> ChatResponse:
    """Send a message to the assistant and receive its answer."""
    if not has_permission(user.role, CHAT_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")

    settings = get_settings()
    try:
        check_rate_limit(
            db,
            "ai",
            f"user:{user.id}",
            settings.ai_rate_limit,
            settings.ai_rate_window_seconds,
            settings=settings,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many assistant requests, please slow down",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    conversation: Conversation | None = None
    if payload.conversation_id is not None:
        conversation = _get_conversation(db, payload.conversation_id, user)
    else:
        conversation = Conversation(owner_id=user.id, title=payload.message.strip()[:80] or "New conversation")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message[:4000])
    db.add(user_message)
    db.commit()

    try:
        response = generate_reply(db, user, payload.message, conversation=conversation, settings=settings)
    except AIQuotaExceeded as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AIError as exc:
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="the assistant is unavailable") from exc

    pending_actions: List[dict[str, Any]] = []
    reply_text = response.text
    suggestion = parse_tool_call(response.text)
    if suggestion is not None:
        try:
            outcome = execute_tool(
                db,
                user,
                suggestion["tool"],
                suggestion["arguments"],
                confirmed=False,
                settings=settings,
            )
            if outcome.get("status") == "requires_confirmation":
                pending_actions.append(outcome)
                reply_text = (
                    "The requested action needs your explicit confirmation before it is executed. "
                    "Review it in the assistant panel and confirm."
                )
            else:
                reply_text = f"Action completed: {outcome.get('tool')}"
        except AIError:
            pending_actions = []

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=reply_text,
        tokens=response.tokens,
    )
    db.add(assistant_message)
    conversation.token_count += response.tokens
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_message)

    audit.record(
        db,
        action="chat.message",
        actor_user_id=user.id,
        target_type="conversation",
        target_id=conversation.id,
        ip=_client_ip(request),
        detail={"provider": response.provider, "tokens": response.tokens},
    )
    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        reply=reply_text,
        tokens_used=response.tokens,
        provider=response.provider,
        pending_actions=pending_actions,
    )


@router.post("/tools/{tool_name}", dependencies=[Depends(enforce_csrf)])
def run_tool(
    tool_name: str,
    payload: dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, Any]:
    """Execute an allow-listed tool.

    Mutating tools require ``confirmed: true``; the assistant itself can never
    set this flag because it never calls this endpoint.
    """
    arguments = (payload or {}).get("arguments") or {}
    if not isinstance(arguments, dict):
        raise HTTPException(status_code=422, detail="invalid arguments")
    confirmed = bool((payload or {}).get("confirmed", False))
    try:
        result = execute_tool(db, user, tool_name, arguments, confirmed=confirmed)
    except AIError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit.record(
        db,
        action="chat.tool",
        actor_user_id=user.id,
        target_type="tool",
        target_id=tool_name,
        ip=_client_ip(request),
        detail={"confirmed": confirmed},
    )
    return result


@router.delete("/conversations/{conversation_id}", dependencies=[Depends(enforce_csrf)])
def delete_conversation(
    conversation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(authenticated_user),
) -> dict[str, bool]:
    """Delete one of the owner's conversations."""
    conversation = _get_conversation(db, conversation_id, user)
    if not has_permission(user.role, CHAT_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permissions")
    db.delete(conversation)
    db.commit()
    audit.record(
        db,
        action="chat.delete_conversation",
        actor_user_id=user.id,
        target_type="conversation",
        target_id=conversation_id,
        ip=_client_ip(request),
    )
    return {"ok": True}


def _get_conversation(db: Session, conversation_id: int, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return conversation


def _client_ip(request: Request) -> str:
    from ..middleware import client_ip as resolve_ip

    return resolve_ip(request)
