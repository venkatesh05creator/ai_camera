"""Chat + quota + memory routes (Phase 3 AI brain)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi import Path as ApiPath
from fastapi.responses import StreamingResponse

from ..ai.providers import ProviderError
from ..config import Settings
from ..dependencies import DbDep, require_csrf, require_user
from ..models.session import Session as SessionRow
from ..models.user import User
from ..schemas import ChatIn, MemoryIn
from ..services import audit_service, chat_service, memory_service
from ..services.auth_service import AuthError
from ..services.memory_service import MemoryError

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _question_from(body: ChatIn) -> str:
    if body.question.strip():
        return body.question.strip()
    texts = [m.content for m in body.messages if m.role == "user"]
    if not texts:
        raise AuthError("empty_chat", "no user message provided", status=422)
    return "\n".join(texts)  # device hints: history validated, last word wins


@router.post("/chat")
async def chat(
    body: ChatIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    request: Request,
    db: DbDep,
) -> dict:
    user, _row = pair
    settings: Settings = request.app.state.settings
    question = _question_from(body)
    try:
        result = await chat_service.answer(
            db, settings, question=question, allow_remote=body.allow_remote)
    except ProviderError:
        await db.commit()
        raise
    await audit_service.record(
        db, "ai.chat", actor_user_id=user.id,
        detail={"allow_remote": body.allow_remote, "provider": result["provider"]})
    await db.commit()
    result["question"] = question
    return result


@router.post("/chat/stream")
async def chat_stream(
    body: ChatIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    request: Request,
    db: DbDep,
):
    user, _row = pair
    settings: Settings = request.app.state.settings
    question = _question_from(body)
    await audit_service.record(
        db, "ai.chat_stream", actor_user_id=user.id,
        detail={"allow_remote": body.allow_remote})
    await db.commit()

    from ..db import get_session_factory

    async def gen() -> AsyncIterator[bytes]:
        try:
            async for event in chat_service.answer_stream(
                    get_session_factory(), settings, question=question,
                    allow_remote=body.allow_remote):
                yield (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")
        except Exception as exc:  # defensive: stream must end honestly
            yield (json.dumps({
                "type": "error", "code": "stream_failed",
                "message": f"chat stream failed ({type(exc).__name__})",
                "status": 500,
            }) + "\n").encode("utf-8")

    return StreamingResponse(
        gen(), media_type="application/x-ndjson",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"})


@router.get("/quota")
async def quota(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
) -> dict:
    from ..ai.router import LLMRouter
    router_obj = LLMRouter(request.app.state.settings)
    rows = await router_obj.summary(db)
    await db.commit()
    return {"rows": rows, "day": rows[0]["day"] if rows else None}


# ------------------------------------------------------------------- memory
memory_router = APIRouter(prefix="/api/memory", tags=["memory"])


@memory_router.get("")
async def memory_list(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
) -> dict:
    settings: Settings = request.app.state.settings
    items = [memory_service.to_public(i, settings)
             for i in await memory_service.list_items(db)]
    await db.commit()
    return {"items": items, "count": len(items)}


@memory_router.post("", status_code=201)
async def memory_create(
    body: MemoryIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    request: Request,
    db: DbDep,
) -> dict:
    user, _row = pair
    settings: Settings = request.app.state.settings
    try:
        item = await memory_service.create_item(
            db, settings, kind=body.kind, text=body.text)
    except MemoryError:
        raise
    await audit_service.record(db, "memory.create", actor_user_id=user.id,
                               target=f"#{item.id}")
    await db.commit()
    return memory_service.to_public(item, settings)


@memory_router.patch("/{item_id}")
async def memory_update(
    body: MemoryIn,
    item_id: Annotated[int, ApiPath(ge=1)],
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    request: Request,
    db: DbDep,
) -> dict:
    user, _row = pair
    settings: Settings = request.app.state.settings
    try:
        item = await memory_service.update_item(
            db, settings, item_id, text=body.text)
    except MemoryError:
        raise
    await audit_service.record(db, "memory.update", actor_user_id=user.id,
                               target=f"#{item_id}")
    await db.commit()
    return memory_service.to_public(item, settings)


@memory_router.delete("/{item_id}")
async def memory_delete(
    item_id: Annotated[int, ApiPath(ge=1)],
    pair: Annotated[tuple[User, SessionRow], Depends(require_csrf)],
    db: DbDep,
) -> dict:
    user, _row = pair
    if not await memory_service.delete_item(db, item_id):
        raise MemoryError("not_found", "memory item not found", 404)
    await audit_service.record(db, "memory.delete", actor_user_id=user.id,
                               target=f"#{item_id}")
    await db.commit()
    return {"ok": True, "id": item_id}


@memory_router.get("/export")
async def memory_export(
    pair: Annotated[tuple[User, SessionRow], Depends(require_user)],
    request: Request,
    db: DbDep,
):
    settings: Settings = request.app.state.settings
    payload = await memory_service.export_json(db, settings)
    await audit_service.record(db, "memory.export", actor_user_id=pair[0].id)
    await db.commit()
    from fastapi import Response
    return Response(
        payload,
        media_type="application/json",
        headers={"content-disposition": 'attachment; filename="aegis-memory.json"'})
