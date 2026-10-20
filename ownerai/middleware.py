"""HTTP middleware: security headers, body limits, HTTPS redirect and logging."""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Awaitable, Callable, Iterable

from fastapi import Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .settings import Settings, get_settings

logger = logging.getLogger("ownerai.access")

SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|csrf|template|embedding|credential)",
    re.IGNORECASE,
)


class RedactingFilter(logging.Filter):
    """Remove obviously sensitive values from log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        if isinstance(record.args, dict):
            record.args = {k: _redact_value(k, v) for k, v in record.args.items()}
        return True


def _redact_value(key: str, value):
    if SENSITIVE_KEY_RE.search(key or ""):
        return "***"
    return value


def _is_html(response: Response) -> bool:
    content_type = response.headers.get("content-type", "")
    return "text/html" in content_type


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach hardening headers to every response."""

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    def _csp(self) -> str:
        connect = ["'self'"]
        for host in self.settings.trusted_hosts:
            if host in {"localhost", "127.0.0.1", "testserver"}:
                connect.append(f"ws://{host}")
                connect.append(f"wss://{host}")
        directives = [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "img-src 'self' data: blob:",
            "media-src 'self' blob:",
            "font-src 'self'",
            "style-src 'self'",
            "script-src 'self'",
            "worker-src 'self' blob:",
            "manifest-src 'self'",
            "connect-src " + " ".join(connect),
        ]
        if self.settings.is_production:
            directives.append("upgrade-insecure-requests")
        return "; ".join(directives)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # noqa: D102
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("Content-Security-Policy", self._csp())
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault(
            "Permissions-Policy",
            "camera=(self), microphone=(), geolocation=(), payment=(), usb=(), "
            "accelerometer=(), gyroscope=(), magnetometer=(), interest-cohort=()",
        )
        headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if self.settings.hsts_enabled:
            include = "; includeSubDomains" if self.settings.hsts_include_subdomains else ""
            headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={self.settings.hsts_max_age}{include}",
            )
        if _is_html(response):
            headers.setdefault("Cache-Control", "no-store, max-age=0")
            headers.setdefault("Pragma", "no-cache")
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Force HTTPS when the deployment requires it."""

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # noqa: D102
        if self.settings.https_only:
            forwarded_proto = request.headers.get("x-forwarded-proto", "") if self.settings.trust_proxy_headers else ""
            scheme = forwarded_proto.split(",")[0].strip().lower() or request.url.scheme
            if scheme != "https":
                url = request.url.replace(scheme="https")
                return RedirectResponse(url=str(url), status_code=307)
        return await call_next(request)


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before they are parsed."""

    def __init__(self, app: ASGIApp, settings: Settings | None = None) -> None:
        super().__init__(app)
        self.settings = settings or get_settings()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # noqa: D102
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse({"error": "invalid_content_length"}, status_code=400)
            if size > self.settings.max_request_body_bytes:
                return JSONResponse(
                    {"error": "payload_too_large", "limit": self.settings.max_request_body_bytes},
                    status_code=413,
                )
        return await call_next(request)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id and emit a redacted access log line."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:  # noqa: D102
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request failed",
                extra={"request_id": request_id, "path": request.url.path, "method": request.method},
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        client = request.client.host if request.client else "unknown"
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "client": _mask_ip(client),
            },
        )
        return response


def _mask_ip(ip: str) -> str:
    """Mask the last octet of an IPv4 address before logging."""
    if not ip or ip in {"unknown", "testclient"}:
        return ip
    if "." in ip:
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3] + ["0"])
    return ip


def client_ip(request: Request) -> str:
    """Resolve the client IP, honouring trusted proxy headers when enabled."""
    settings = get_settings()
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:256]


def apply_cors(app, settings: Settings | None = None) -> None:
    """Attach a restrictive CORS middleware when origins are configured."""
    from fastapi.middleware.cors import CORSMiddleware

    settings = settings or get_settings()
    origins: Iterable[str] = settings.cors_origins
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
