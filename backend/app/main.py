"""FastAPI Application Entrypoint for the Full-Stack Surveillance Platform."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.v1.ai import router as ai_router
from .api.v1.alerts import router as alerts_router
from .api.v1.audit import router as audit_router
from .api.v1.auth import router as auth_router
from .api.v1.cameras import router as cameras_router
from .api.v1.events import router as events_router
from .api.v1.people import router as people_router
from .api.v1.reports import router as reports_router
from .api.v1.stream import router as stream_router
from .core.config import get_settings
from .core.database import Base, SessionLocal, engine
from .core.security import hash_password
from .models.entities import Camera, Person, User
from .services.consent_service import grant_consent
from .workers.inference_worker import worker_registry

logger = logging.getLogger("surveillance")
logging.basicConfig(level=logging.INFO)


def _seed_initial_data():
    """Create tables and seed initial default administrator and camera."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 1. Admin user
        admin = db.query(User).filter_by(role="owner").first()
        if not admin:
            settings = get_settings()
            admin_email = os.environ.get("INITIAL_ADMIN_EMAIL", "admin@surveillance.local")
            admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD")
            if not admin_password:
                if settings.app_env == "production":
                    raise RuntimeError("INITIAL_ADMIN_PASSWORD must be configured in production environment.")
                admin_password = "admin123456"
                logger.warning("Initializing default system owner account with development credentials (%s).", admin_email)
            else:
                logger.info("Initializing default system owner account (%s).", admin_email)

            admin = User(
                email=admin_email,
                password_hash=hash_password(admin_password),
                display_name="System Owner",
                role="owner",
                status="active",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Default laptop webcam
        cam = db.query(Camera).filter_by(source_type="webcam").first()
        if not cam:
            cam = Camera(
                name="Laptop Primary Webcam",
                source_type="webcam",
                location_label="Workstation Primary",
                status="online",
                stream_url="0",
                owner_user_id=admin.id,
            )
            db.add(cam)
            db.commit()
            logger.info("Registered default laptop camera (Index 0)")

        # 3. Seed an initial profile from legacy datastore if available
        p_count = db.query(Person).count()
        if p_count == 0:
            p1 = Person(
                name="Authorized Owner",
                age=32,
                gender="Not Disclosed",
                role_relationship="owner",
                contact_details="owner@surveillance.local",
                notes="Primary installation owner with consent for verification.",
                status="enrolled",
            )
            db.add(p1)
            db.commit()
            db.refresh(p1)
            grant_consent(db, p1.id, recorded_by_user_id=admin.id)
            logger.info("Seeded initial authorized owner profile with explicit consent")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_initial_data()
    yield
    worker_registry.stop_all()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Cross-platform, privacy-first AI Surveillance Backend",
        version="2.0.0",
        lifespan=lifespan,
    )

    # Trusted Host Protection
    hosts = settings.trusted_hosts if isinstance(settings.trusted_hosts, list) else [settings.trusted_hosts]
    if hosts and "*" not in hosts:
        from fastapi.middleware.trustedhost import TrustedHostMiddleware
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

    # CORS Protection
    cors_origins = settings.cors_origins if isinstance(settings.cors_origins, list) else [settings.cors_origins]
    allow_all_origins = "*" in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not allow_all_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    # Routers
    api_prefix = settings.api_prefix
    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(cameras_router, prefix=api_prefix)
    app.include_router(people_router, prefix=api_prefix)
    app.include_router(events_router, prefix=api_prefix)
    app.include_router(alerts_router, prefix=api_prefix)
    app.include_router(reports_router, prefix=api_prefix)
    app.include_router(audit_router, prefix=api_prefix)
    app.include_router(stream_router, prefix=api_prefix)
    app.include_router(ai_router, prefix=api_prefix)

    # Health check
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "version": "2.0.0"}

    # Holographic Iron Man HUD (JARVIS 3D Workplace)
    @app.get("/hud", response_class=HTMLResponse)
    def serve_hud():
        """Serves the 3D Holographic Iron Man HUD interface."""
        candidates = [
            Path("ownerai/templates/hud.html"),
            Path(__file__).resolve().parent.parent.parent / "ownerai" / "templates" / "hud.html",
        ]
        for p in candidates:
            if p.exists():
                return HTMLResponse(content=p.read_text(encoding="utf-8"))
        return HTMLResponse("<h2>Holographic HUD template not found</h2>", status_code=404)

    @app.get("/api/state")
    @app.get("/api/hud/state")
    @app.get(f"{api_prefix}/hud/state")
    def get_hud_state_endpoint(lv: int = 0):
        """Returns live system telemetry, audio visualizer wave, and market quotes for the HUD."""
        from .services.hud_service import get_hud_state_data
        return JSONResponse(content=get_hud_state_data(lv=lv))

    # Mount Web build if present
    dist_dir = Path("web/dist")
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
