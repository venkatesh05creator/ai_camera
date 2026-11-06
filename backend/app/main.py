"""Aegis AI application factory (Phase 2: secure foundation).

Boot refuse-safe in production, loopback bind by default, strict security
headers, request body limit, structured logging, and a health endpoint that
reports only real measured values.
"""

from __future__ import annotations

import logging
import platform
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from . import db
from . import globals as app_globals
from .config import PROJECT_ROOT, Settings, get_settings
from .logging_setup import setup_logging
from .middleware import (
    ApiRateLimitMiddleware,
    HTTPSRedirectMiddleware,
    PanicMiddleware,
    RequestBodyLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from .services.auth_service import AuthError

STARTED_AT = time.time()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level,
                  json_logs=settings.json_logs,
                  log_dir=PROJECT_ROOT / "var" / "logs")

    if settings.app_env == "production":
        problems = settings.production_problems()
        if problems:
            for problem in problems:
                print(f"CONFIG PROBLEM: {problem}", file=sys.stderr)
            raise SystemExit("refusing to start in production with configuration problems")
    elif not settings.secret_key.get_secret_value():
        logging.getLogger(__name__).warning(
            "report: no OWNERAI_SECRET_KEY set - dev fallback used "
            "(production would refuse to start)")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app_globals.reset_panic()
        db.get_engine(settings)
        db.get_session_factory()
        from .models.base import create_all
        await create_all()
        from .services.camera_service import purge_expired
        factory = db.get_session_factory()
        async with factory() as session:  # startup retention sweep (honest counts)
            removed = await purge_expired(session)
            if any(removed.values()):
                logging.getLogger(__name__).info("report: retention purge %s", removed)
            await session.commit()
        yield
        await db.dispose_engine()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if settings.app_env == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.app_env == "production" else "/openapi.json",
    )
    app.state.settings = settings
    app.state.panic = {"active": False, "until": None, "reason": None}

    # --- middleware (outermost first) --------------------------------------
    # NOTE: starlette runs the LAST-added middleware first (outermost).
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(ApiRateLimitMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(HTTPSRedirectMiddleware, enabled=settings.https_only)
    app.add_middleware(PanicMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["X-CSRF-Token", "Content-Type", "Authorization"],
        )

    # --- panic state shared with PanicMiddleware -----------------------------
    app.state.panic = app_globals.PANIC

    # --- routers --------------------------------------------------------------
    from .routers import ai as ai_router
    from .routers import auth as auth_router
    from .routers import cameras as cameras_router
    from .routers import people as people_router
    from .routers import system as system_router
    app.include_router(auth_router.router)
    app.include_router(ai_router.router)
    app.include_router(ai_router.memory_router)
    app.include_router(cameras_router.router)
    app.include_router(cameras_router.notifications_router)
    app.include_router(people_router.router)
    app.include_router(system_router.router)

    # --- health: REAL metrics only ------------------------------------------
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> JSONResponse:
        db_health = await db.check_database()
        return JSONResponse({
            "status": "ok" if db_health.get("reachable") else "degraded",
            "app_env": settings.app_env,
            "uptime_seconds": round(time.time() - STARTED_AT, 2),
            "python": platform.python_version(),
            "panic_active": bool(app_globals.PANIC.get("active")),
            "db": db_health,
        })

    # --- error handling -------------------------------------------------------
    from .ai.providers import ProviderError
    from .services.camera_service import CameraError
    from .services.memory_service import MemoryError

    @app.exception_handler(AuthError)
    async def auth_error(request: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(MemoryError)
    async def memory_error(request: Request, exc: MemoryError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(CameraError)
    async def camera_error(request: Request, exc: CameraError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}})

    from .services.people_service import PeopleError

    @app.exception_handler(PeopleError)
    async def people_error(request: Request, exc: PeopleError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(ProviderError)
    async def provider_error(request: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logging.getLogger(__name__).exception(
            "unhandled error rid=%s", request_id)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error",
                               "message": "Something went wrong. The error has been logged.",
                               "request_id": request_id}})

    # --- built PWA from the same origin (skips silently when absent) ----------
    import os as _os

    from fastapi.responses import FileResponse

    web_dist = Path(_os.environ.get("AEGIS_WEB_DIST",
                                     PROJECT_ROOT / "web" / "dist"))
    if web_dist.is_dir():
        web_root = web_dist.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse | JSONResponse:  # noqa: B008
            if full_path.startswith(("api/", "api")) or full_path == "healthz":
                return JSONResponse(
                    status_code=404,
                    content={"error": {"code": "not_found", "message": "Not found"}})
            candidate = (web_root / full_path).resolve() if full_path else web_root
            if (full_path and candidate.is_file()
                    and candidate.is_relative_to(web_root)):
                return FileResponse(candidate, headers={"cache-control": "no-cache"})
            return FileResponse(web_root / "index.html",
                                headers={"cache-control": "no-cache"})

    return app
