"""Pure-ASGI middleware: request context, request-body limit, security headers.

Order (outermost first): RequestBodyLimit -> RequestContext -> SecurityHeaders.
All are dependency-free and framework-agnostic so they run before FastAPI
routing ever sees the request.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import Settings

logger = logging.getLogger("aegis.request")


class RequestBodyLimitMiddleware:
    """Reject requests whose body exceeds ``max_bytes`` *before* parsing.

    Handles both the (common) declared ``content-length`` header and the
    chunked case by counting streamed bytes.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            await _send_413(send)
            return

        received = 0
        exceeded = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    return {"type": "http.request", "body": b"", "more_body": True}
            return message

        if scope.get("method") in ("POST", "PUT", "PATCH"):
            sent_rejection = False

            async def guarded_send(message: Message) -> None:
                nonlocal sent_rejection
                if exceeded and message["type"] == "http.response.start" and not sent_rejection:
                    sent_rejection = True
                    # drain remaining request body so client can parse our reply
                    while True:
                        more = await receive()
                        if more["type"] == "http.disconnect" or more["type"] == "http.request" and not more.get("more_body"):
                            break
                    await _send_413(send)
                    return
                await send(message)

            try:
                await self.app(scope, limited_receive, guarded_send)
                if exceeded and not sent_rejection:
                    sent_rejection = True
                    await _send_413(send)
            except Exception:
                if exceeded and not sent_rejection:
                    await _send_413(send)
                else:
                    raise
            return

        await self.app(scope, limited_receive, send)


async def _send_413(send: Send) -> None:
    body = json.dumps({"error": {"code": "payload_too_large",
                                 "message": "Request body too large"}}).encode()
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class RequestContextMiddleware:
    """Attach a fresh ``request_id`` to every request and log it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:16]
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        started = datetime.now(UTC)
        try:
            await self.app(scope, receive, send_with_id)
        finally:
            duration_ms = (datetime.now(UTC) - started).total_seconds() * 1000
            logger.info("%s %s -> %s ms rid=%s",
                        scope.get("method"), scope.get("path"),
                        round(duration_ms, 1), request_id,
                        extra={"request_id": request_id})


class HTTPSRedirectMiddleware:
    """Redirect plain http -> https when OWNERAI_HTTPS_ONLY (dev-friendly)."""

    def __init__(self, app: ASGIApp, enabled: bool) -> None:
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and self.enabled:
            headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                       for k, v in scope.get("headers", [])}
            proto = headers.get("x-forwarded-proto", scope.get("scheme", "http"))
            if proto != "https":
                host = headers.get("host", "localhost")
                path = scope.get("path", "/")
                query = f"?{scope['query_string'].decode()}" if scope.get("query_string") else ""
                body = json.dumps({"error": {"code": "upgrade_required",
                                             "message": "HTTPS required"}}).encode()
                await send({"type": "http.response.start", "status": 426,
                            "headers": [(b"content-type", b"application/json"),
                                        (b"content-length", str(len(body)).encode()),
                                        (b"location", f"https://{host}{path}{query}".encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def security_headers(settings: Settings) -> dict[str, str]:
    headers = {
        "Content-Security-Policy": (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'self'"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(self), microphone=(self), geolocation=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    if settings.hsts_enabled and (settings.https_only or settings.app_env == "production"):
        headers["Strict-Transport-Security"] = \
            f"max-age={settings.hsts_max_age_seconds}; includeSubDomains"
    return headers


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.headers = security_headers(settings)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {k.lower() for k, _ in headers}
                for name, value in self.headers.items():
                    if name.lower().encode() not in existing:
                        headers.append((name.lower().encode(), value.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
