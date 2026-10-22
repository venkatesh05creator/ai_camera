"""Authentication, password hashing, and role-based permissions."""

from __future__ import annotations

import enum
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .config import get_settings

logger = logging.getLogger(__name__)

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# Permissions
PERM_CAMERAS_READ = "cameras:read"
PERM_CAMERAS_WRITE = "cameras:write"
PERM_PEOPLE_READ = "people:read"
PERM_PEOPLE_WRITE = "people:write"
PERM_CONSENT_MANAGE = "consent:manage"
PERM_EVENTS_READ = "events:read"
PERM_EVENTS_MANAGE = "events:manage"
PERM_REPORTS_READ = "reports:read"
PERM_AUDIT_READ = "audit:read"
PERM_ADMIN_MANAGE = "admin:manage"

ROLE_PERMISSIONS: Dict[Role, set[str]] = {
    Role.OWNER: {
        PERM_CAMERAS_READ, PERM_CAMERAS_WRITE,
        PERM_PEOPLE_READ, PERM_PEOPLE_WRITE, PERM_CONSENT_MANAGE,
        PERM_EVENTS_READ, PERM_EVENTS_MANAGE,
        PERM_REPORTS_READ, PERM_AUDIT_READ, PERM_ADMIN_MANAGE,
    },
    Role.ADMIN: {
        PERM_CAMERAS_READ, PERM_CAMERAS_WRITE,
        PERM_PEOPLE_READ, PERM_PEOPLE_WRITE, PERM_CONSENT_MANAGE,
        PERM_EVENTS_READ, PERM_EVENTS_MANAGE,
        PERM_REPORTS_READ, PERM_AUDIT_READ,
    },
    Role.OPERATOR: {
        PERM_CAMERAS_READ,
        PERM_PEOPLE_READ,
        PERM_EVENTS_READ, PERM_EVENTS_MANAGE,
        PERM_REPORTS_READ,
    },
    Role.VIEWER: {
        PERM_CAMERAS_READ,
        PERM_EVENTS_READ,
    },
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except Exception:
        return None


def has_permission(user_role: str, permission: str) -> bool:
    try:
        role_enum = Role(user_role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, set())


def validate_stream_url(url: Optional[str], source_type: str = "webcam") -> tuple[bool, str]:
    """Validate camera stream URLs to prevent SSRF and unauthorized network scans."""
    if source_type == "webcam":
        if url is None or url == "" or url.isdigit():
            return True, "Valid webcam index"
        return False, "Webcam source requires an integer device index (e.g. 0, 1, 2)"

    if not url or not isinstance(url, str):
        return False, "Stream URL cannot be empty"

    url_clean = url.strip()

    # Allow local test video file paths
    if url_clean.endswith((".mp4", ".avi", ".mkv", ".mov")) and "://" not in url_clean:
        return True, "Local video file"

    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url_clean)
    except Exception:
        return False, "Malformed stream URL"

    allowed_schemes = {"rtsp", "rtsps", "http", "https"}
    if parsed.scheme.lower() not in allowed_schemes:
        return False, f"Unsupported stream scheme '{parsed.scheme}'. Allowed: rtsp, rtsps, http, https"

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "Missing hostname in stream URL"

    netloc = (parsed.netloc or "").lower().strip()
    # Block AWS/GCP/Azure link-local cloud metadata endpoints and loopbacks in cloud/container environments
    blocked_hosts = {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata",
        "169.254.170.2",
        "fd00:ec2::254",
        "::ffff:169.254.169.254",
    }
    if any(b in netloc or b in hostname for b in blocked_hosts) or hostname.startswith("169.254."):
        return False, "Access to cloud metadata and link-local addresses is prohibited (SSRF protection)"

    # Robust IP representation parsing (decimal integer, hex, octal, standard dotted quad)
    import ipaddress
    import socket

    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            if hostname.isdigit():
                ip_obj = ipaddress.ip_address(int(hostname))
            elif hostname.startswith("0x"):
                ip_obj = ipaddress.ip_address(int(hostname, 16))
            elif hostname.startswith("0") and len(hostname) > 1 and not hostname.startswith("0."):
                ip_obj = ipaddress.ip_address(int(hostname, 8))
        except (ValueError, OverflowError):
            pass

    if ip_obj is not None:
        if (
            ip_obj.is_link_local
            or ip_obj.is_reserved
            or str(ip_obj).startswith("169.254.")
            or str(ip_obj) in blocked_hosts
        ):
            return False, "Access to cloud metadata and link-local addresses is prohibited (SSRF protection)"
    else:
        # Resolve hostname to detect DNS-based metadata / link-local redirection
        try:
            infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
            for info in infos:
                addr_str = info[4][0]
                try:
                    addr_obj = ipaddress.ip_address(addr_str)
                    if (
                        addr_obj.is_link_local
                        or addr_obj.is_reserved
                        or str(addr_obj).startswith("169.254.")
                        or str(addr_obj) in blocked_hosts
                    ):
                        return False, "Access to cloud metadata and link-local addresses is prohibited (SSRF protection)"
                except ValueError:
                    continue
        except socket.gaierror:
            pass

    return True, "Valid stream URL"


def redact_stream_url(url: Optional[str]) -> str:
    """Redact passwords and user credentials from stream URLs for safe logging."""
    if not url or "@" not in url:
        return url or ""
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.password:
            user = parsed.username or ""
            netloc = f"{user}:***@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return parsed._replace(netloc=netloc).geturl()
    except Exception as exc:
        logger.debug("Failed parsing stream url in redact_stream_url: %s", exc)
    import re
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", url)

