"""Panic switch, audit verification, rate-limit status (system routes)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from ..dependencies import DbDep, require_owner, require_owner_csrf
from ..models.session import Session as SessionRow
from ..models.user import User
from ..schemas import AuditVerifyOut, PanicIn
from ..services import audit_service, rate_limit

router = APIRouter(prefix="/api/system", tags=["system"])


@router.post("/panic", response_model=dict)
async def panic_on(
    body: PanicIn,
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner_csrf)],
    request: Request,
    db: DbDep,
) -> dict:
    from .. import globals as app_globals

    user, _row = pair
    app_globals.PANIC["active"] = True
    app_globals.PANIC["reason"] = body.reason
    request.app.state.panic = dict(app_globals.PANIC)
    await audit_service.record(
        db, "system.panic_on", actor_user_id=user.id,
        detail={"reason": body.reason[:300]})
    await db.commit()
    return {"ok": True, "panic_active": True}


@router.post("/panic/clear", response_model=dict)
async def panic_off(
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner_csrf)],
    request: Request,
    db: DbDep,
) -> dict:
    from .. import globals as app_globals

    user, _row = pair
    app_globals.reset_panic()
    request.app.state.panic = dict(app_globals.PANIC)
    await audit_service.record(db, "system.panic_off", actor_user_id=user.id)
    await db.commit()
    return {"ok": True, "panic_active": False}


@router.get("/audit/verify", response_model=AuditVerifyOut)
async def audit_verify(
    _pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    db: DbDep,
) -> AuditVerifyOut:
    result = await audit_service.verify_chain(db)
    return AuditVerifyOut(**result)


@router.get("/ratelimit/{bucket:path}", response_model=dict)
async def ratelimit_status(
    bucket: str,
    pair: Annotated[tuple[User, SessionRow], Depends(require_owner)],
    request: Request,
    db: DbDep,
) -> dict:
    user, _row = pair
    settings = request.app.state.settings
    total = await rate_limit.count_hits(db, bucket,
                                        settings.api_rate_window_seconds)
    await audit_service.record(
        db, "system.ratelimit_status", actor_user_id=user.id,
        target=bucket[:200])
    await db.commit()
    return {"bucket": bucket, "hits_in_window": total,
            "limit": settings.api_rate_limit}
