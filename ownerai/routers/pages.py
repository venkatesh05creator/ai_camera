"""HTML pages (server rendered) for the dashboard, the landing page and the admin area."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..rbac import ADMIN_AUDIT, has_permission
from ..services.search import count_resources
from ..sessions import current_session_from_request, ensure_csrf_cookie
from ..settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pages"])

TEMPLATES_DIR = "templates"

_templates_path = Path(__file__).resolve().parent.parent / TEMPLATES_DIR
templates = Jinja2Templates(directory=str(_templates_path))


def _base_context(request: Request, db: Session, **extra: Any) -> Dict[str, Any]:
    settings = get_settings()
    session = current_session_from_request(request, db)
    user = session.user if session else None
    context: Dict[str, Any] = {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "request": request,
        "user": user,
        "session": session,
        "csrf_token": session.csrf_token if session else "",
        "permissions": _permission_set(user),
        "support_destination": settings.support_destination,
        "is_admin": bool(user and has_permission(user.role, ADMIN_AUDIT)),
    }
    context.update(extra)
    return context


def _permission_set(user: Optional[User]) -> set:
    from ..rbac import permissions_for

    if user is None:
        return set()
    return set(permissions_for(user.role))


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Public landing page."""
    context = _base_context(request, db)
    return _render(request, "index.html", context)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Login page."""
    context = _base_context(request, db)
    return _render(request, "login.html", context)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Registration page."""
    context = _base_context(request, db)
    return _render(request, "register.html", context)


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Password reset request page."""
    context = _base_context(request, db)
    return _render(request, "forgot_password.html", context)


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Password reset completion page."""
    context = _base_context(request, db)
    token = request.query_params.get("token", "")
    context["token"] = token
    return _render(request, "reset_password.html", context)


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """E-mail confirmation page."""
    context = _base_context(request, db)
    context["token"] = request.query_params.get("token", "")
    return _render(request, "verify_email.html", context)


@router.get("/docs", response_class=HTMLResponse)
def docs_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """Help and documentation page."""
    context = _base_context(request, db)
    from ..services.search import HELP_DOCS

    context["docs"] = HELP_DOCS
    return _render(request, "docs.html", context)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """The owner dashboard."""
    session = current_session_from_request(request, db)
    if session is None:
        return RedirectResponse(url="/login?next=/dashboard", status_code=303)
    context = _base_context(request, db)
    context["counts"] = count_resources(db, session.user)
    # The voice interface needs the microphone.  The permission is granted for
    # this page only - every other page keeps ``microphone=()``.
    return _render(
        request,
        "dashboard.html",
        context,
        headers={
            "Permissions-Policy": (
                "camera=(self), microphone=(self), geolocation=(), payment=(), usb=(), "
                "accelerometer=(), gyroscope=(), magnetometer=(), interest-cohort=()"
            )
        },
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    """The administration console."""
    session = current_session_from_request(request, db)
    if session is None:
        return RedirectResponse(url="/login?next=/admin", status_code=303)
    if not has_permission(session.user.role, ADMIN_AUDIT):
        return RedirectResponse(url="/dashboard", status_code=303)
    context = _base_context(request, db)
    return _render(request, "admin.html", context)


@router.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    """Minimal health probe that does not disclose internal details."""
    settings = get_settings()
    return JSONResponse(
        {"status": "ok", "version": settings.app_version, "environment": settings.app_env},
        headers={"Cache-Control": "no-store"},
    )


def _render(
    request: Request,
    template: str,
    context: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> HTMLResponse:
    # The cookie must be attached to the response that is actually returned -
    # FastAPI only merges the headers of the injected ``response`` object when
    # the endpoint returns a plain body.
    page = templates.TemplateResponse(request, template, context)
    ensure_csrf_cookie(request, page, get_settings(), context.get("session"))
    for name, value in (headers or {}).items():
        page.headers[name] = value
    return page
