"""Authentication router: register, login, current user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.ratelimit import login_limiter
from ...core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from ...models.entities import User
from ...schemas.schemas import TokenResponse, UserLogin, UserOut, UserRegister
from ...services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = payload["sub"]
    user = db.get(User, user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.scalars(select(User).where(User.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # If first user in database, grant owner role automatically
    user_count = db.scalar(select(func.count(User.id))) or 0
    assigned_role = "owner" if user_count == 0 else (payload.role or "operator")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.email.split("@")[0],
        role=assigned_role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(db, action="auth.register", resource_type="user", resource_id=user.id, details={"email": user.email, "role": user.role})
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    allowed_ip, retry_after_ip = login_limiter.check(f"ip:{client_ip}", max_requests=10, window_seconds=60)
    allowed_email, retry_after_email = login_limiter.check(f"email:{payload.email.lower()}", max_requests=5, window_seconds=60)
    if not allowed_ip or not allowed_email:
        retry_after = max(retry_after_ip, retry_after_email)
        log_action(db, action="auth.login.rate_limited", resource_type="user", outcome="blocked", details={"email": payload.email, "client_ip": client_ip})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.scalars(select(User).where(User.email == payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        log_action(db, action="auth.login", resource_type="user", outcome="failed", details={"email": payload.email})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": user.id, "role": user.role, "email": user.email})
    log_action(db, action="auth.login", resource_type="user", actor_user_id=user.id, resource_id=user.id)
    return TokenResponse(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user
