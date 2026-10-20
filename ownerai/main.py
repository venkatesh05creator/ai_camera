"""FastAPI application factory."""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .db import init_db, session_scope
from .middleware import (
    HTTPSRedirectMiddleware,
    RedactingFilter,
    RequestBodyLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    apply_cors,
)
from .models import Device
from .routers import admin, auth, chat, contact, devices, events, identities, legacy, pages, search
from .sessions import session_from_token
from .settings import get_settings

logger = logging.getLogger("ownerai")

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structured logging without secrets."""
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
    logging.getLogger().addFilter(RedactingFilter())


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line (no secrets, no raw bodies)."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in (
            "request_id",
            "method",
            "path",
            "status",
            "duration_ms",
            "client",
            "action",
            "actor_user_id",
            "target_type",
            "target_id",
            "outcome",
            "user_id",
            "role",
            "permission",
            "scope",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info).splitlines()[-1][:300]
        return json.dumps(payload, default=str)


def create_app(settings=None) -> FastAPI:
    """Build the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.json_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings)
        logger.info("application started", extra={"version": __version__, "environment": settings.app_env})
        yield
        logger.info("application stopped")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Privacy-first, owner-only AI camera assistant.",
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None if settings.is_production else "/api/redoc",
        openapi_url=None if settings.is_production else "/api/openapi.json",
        debug=False,
        lifespan=lifespan,
    )

    # --- middleware (executed bottom-up) ---------------------------------
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(RequestBodyLimitMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(HTTPSRedirectMiddleware, settings=settings)
    apply_cors(app, settings)

    # --- routers ---------------------------------------------------------
    app.include_router(auth.router)
    app.include_router(devices.router)
    app.include_router(events.router)
    app.include_router(identities.router)
    app.include_router(chat.router)
    app.include_router(search.router)
    app.include_router(admin.router)
    app.include_router(legacy.router)
    app.include_router(contact.router)
    app.include_router(pages.router)

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- error handling --------------------------------------------------
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            {"error": "request_failed", "detail": exc.detail},
            status_code=exc.status_code,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Only field names and messages are returned - no payload echo.
        errors = [
            {"field": ".".join(str(part) for part in error.get("loc", [])[1:]), "message": error.get("msg", "invalid")}
            for error in exc.errors()
        ]
        return JSONResponse({"error": "validation_error", "details": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover - safety net
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(
            {"error": "internal_error", "detail": "the request could not be processed"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --- websocket -------------------------------------------------------
    @app.websocket("/ws/events")
    async def events_socket(websocket: WebSocket):
        token = websocket.cookies.get(settings.session_cookie_name)
        with session_scope(settings) as db:
            session = session_from_token(db, token) if token else None
            user = session.user if session else None
            if session is None or user is None or not user.is_active:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            user_id = user.id
            role = user.role

        await websocket.accept()
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except ValueError:
                    await websocket.send_json({"type": "error", "detail": "invalid message"})
                    continue
                if not isinstance(message, dict):
                    await websocket.send_json({"type": "error", "detail": "invalid message"})
                    continue
                await _handle_socket_message(websocket, message, user_id, role, settings)
        except WebSocketDisconnect:
            return
        except Exception:  # pragma: no cover - defensive
            logger.exception("websocket failure")
            return

    return app


async def _handle_socket_message(
    websocket: WebSocket, message: Dict[str, Any], user_id: int, role: str, settings
) -> None:
    """Authorise and answer a WebSocket message."""
    action = message.get("action")
    if action == "ping":
        await websocket.send_json({"type": "pong"})
        return
    if action == "subscribe":
        device_ids = message.get("device_ids") or []
        if not isinstance(device_ids, list):
            await websocket.send_json({"type": "error", "detail": "invalid device list"})
            return
        allowed = []
        with session_scope(settings) as db:
            for raw_id in device_ids[:50]:
                try:
                    device_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                device = db.get(Device, device_id)
                if device is not None and device.owner_id == user_id:
                    allowed.append(device_id)
        await websocket.send_json({"type": "subscribed", "device_ids": allowed})
        return
    if action == "unsubscribe":
        await websocket.send_json({"type": "unsubscribed"})
        return
    await websocket.send_json({"type": "error", "detail": "unsupported action"})


app = create_app()
