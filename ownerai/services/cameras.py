"""Camera helpers: safe snapshot fetching and device authentication.

Network access performed on behalf of a user is treated as attacker
controlled.  Every URL is validated before a socket is opened:

* only ``http``/``https`` are accepted, no user-info in the URL,
* the host must resolve to a public IP address unless it was explicitly
  allow-listed by the operator (private IP ranges are the classic SSRF
  target),
* redirects are followed manually and re-validated, with a hard limit,
* responses must be an image and are capped in size and time.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}


class CameraFetchError(RuntimeError):
    """Raised when a snapshot cannot be retrieved safely."""


class UnsafeURLError(CameraFetchError):
    """Raised when a URL points at a forbidden destination."""


@dataclass(frozen=True)
class SnapshotResult:
    """A validated camera snapshot."""

    content: bytes
    content_type: str
    url: str


def _is_private_address(host: str) -> bool:
    """Return ``True`` when the host is not a routable public address."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not address.is_global


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError("the camera host could not be resolved") from exc
    return sorted({info[4][0] for info in infos})


def validate_camera_url(url: str, settings: Optional[Settings] = None) -> str:
    """Validate a camera URL and return its normalised form."""
    settings = settings or get_settings()
    if not url or len(url) > 2048:
        raise UnsafeURLError("invalid camera URL")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("only http and https camera URLs are supported")
    if parsed.username or parsed.password:
        raise UnsafeURLError("credentials in camera URLs are not allowed")
    host = (parsed.hostname or "").strip()
    if not host:
        raise UnsafeURLError("the camera URL has no host")
    if host.lower() in {"localhost", "ip6-localhost"} or host.lower().endswith(".local"):
        allowed = {item.lower() for item in settings.allow_private_camera_hosts}
        if host.lower() not in allowed:
            raise UnsafeURLError("private camera hosts are not allowed by default")

    if host.lower() not in {item.lower() for item in settings.allow_private_camera_hosts}:
        addresses = _resolve(host)
        if not addresses:
            raise UnsafeURLError("the camera host could not be resolved")
        for address in addresses:
            if _is_private_address(address):
                raise UnsafeURLError(
                    "the camera host resolves to a private or reserved address"
                )
    return url


def fetch_snapshot(url: str, settings: Optional[Settings] = None) -> SnapshotResult:
    """Download a single camera snapshot with strict limits."""
    settings = settings or get_settings()
    current = validate_camera_url(url, settings)
    deadline = time.monotonic() + settings.camera_fetch_timeout_seconds

    with httpx.Client(
        timeout=settings.camera_fetch_timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for _ in range(settings.camera_max_redirects + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise CameraFetchError("the camera did not answer in time")
            try:
                with client.stream("GET", current, timeout=remaining) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise CameraFetchError("the camera returned an invalid redirect")
                        current = validate_camera_url(
                            str(httpx.URL(current).join(location)), settings
                        )
                        continue
                    if response.status_code >= 400:
                        raise CameraFetchError(f"the camera returned HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type not in ALLOWED_CONTENT_TYPES:
                        raise CameraFetchError("the camera did not return an image")
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > settings.camera_max_bytes:
                        raise CameraFetchError("the camera image is too large")
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > settings.camera_max_bytes:
                            raise CameraFetchError("the camera image is too large")
                    return SnapshotResult(
                        content=bytes(chunks), content_type=content_type, url=current
                    )
            except httpx.HTTPError as exc:
                raise CameraFetchError("the camera could not be reached") from exc
    raise CameraFetchError("too many redirects")


# ---------------------------------------------------------------------------
# Device authentication for event ingestion
# ---------------------------------------------------------------------------
def generate_device_token() -> str:
    """Create a device bearer token."""
    from ..crypto import random_token

    return random_token(32)


def hash_device_token(token: str) -> str:
    """Hash a device token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_device_request(secret: str, timestamp: str, nonce: str, body: bytes) -> str:
    """Create the HMAC signature for an event ingestion request."""
    message = b".".join(
        [timestamp.encode("utf-8"), nonce.encode("utf-8"), hashlib.sha256(body).hexdigest().encode("utf-8")]
    )
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_device_signature(
    secret: str, timestamp: str, nonce: str, body: bytes, signature: str, *, max_age: int = 300
) -> bool:
    """Validate the timestamp window and the HMAC of an ingestion request."""
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if abs(now - sent_at) > max_age:
        return False
    expected = sign_device_request(secret, timestamp, nonce, body)
    return hmac.compare_digest(expected, signature or "")


def purge_expired_nonces(db, max_age_seconds: int = 300) -> int:
    """Delete device nonces older than the maximum allowable drift window."""
    from datetime import datetime, timedelta, timezone
    from ..models import DeviceNonce

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
    removed = db.query(DeviceNonce).filter(DeviceNonce.created_at < cutoff).delete()
    db.commit()
    return int(removed)
