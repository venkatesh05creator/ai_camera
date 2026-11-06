"""SSRF-safe URL validation for outbound fetches (camera feeds etc.).

Rules:
- only http / https
- no username:password@ userinfo
- host must resolve via DNS; EVERY resolved address must be a global
  (non-private, non-loopback, non-link-local, non-reserved, non-multicast)
  address unless ``allow_private`` is explicitly enabled
- callers MUST dial the returned IP (not re-resolve the hostname) to prevent
  DNS-rebinding races; ``ResolvedUrl.ip`` is the address to connect to

The resolver is injectable so tests never touch the network.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver: TypeAlias = Callable[[str, int], list]


class SSRFError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedUrl:
    url: str
    scheme: str
    host: str
    ip: str
    port: int
    path: str


_resolver: Resolver = socket.getaddrinfo  # type: ignore[assignment]

DEFAULT_TIMEOUT = 10.0


def _set_resolver(fn: Resolver) -> None:
    global _resolver
    _resolver = fn


def _is_forbidden(ip: IPAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        # IPv4-mapped IPv6 (::ffff:10.0.0.5) would smuggle private ranges
        or (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None)
    )


def validate_url(
    url: str,
    *,
    allow_private: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
    port_whitelist: tuple[int, ...] | None = None,
) -> ResolvedUrl:
    """Validate + resolve ``url``; raises :class:`SSRFError` on any violation."""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError as exc:
        raise SSRFError("URL could not be parsed") from exc

    if parsed.scheme not in ("http", "https"):
        raise SSRFError(f"scheme '{parsed.scheme}' not allowed (use http/https)")
    host = parsed.hostname
    if not host:
        raise SSRFError("URL has no host")
    if parsed.username or parsed.password:
        raise SSRFError("URLs with embedded credentials are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port_whitelist is not None and port not in port_whitelist:
        raise SSRFError(f"port {port} not allowed")
    if len(url) > 2048:
        raise SSRFError("URL too long")

    host_literal = _maybe_ip(host)
    if host_literal is not None:
        addresses = [host_literal]
    else:
        try:
            infos = _resolver(host, port)
        except (socket.gaierror, TimeoutError, OSError) as exc:
            raise SSRFError(f"host '{host}' could not be resolved") from exc
        addresses = []
        for info in infos:
            addr = _maybe_ip(str(info[4][0]))
            if addr is not None:
                addresses.append(addr)
        if not addresses:
            raise SSRFError(f"host '{host}' resolved to no usable address")

    for addr in addresses:
        if not allow_private and _is_forbidden(addr):
            raise SSRFError(
                f"host '{host}' resolves to a private/forbidden address; "
                "blocked for SSRF safety"
            )

    path = parsed.path or "/"
    return ResolvedUrl(
        url=url, scheme=parsed.scheme, host=host, ip=str(addresses[0]),
        port=port, path=path,
    )


def _maybe_ip(value: str) -> IPAddress | None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    # literal bracketed IPv6 arrives without brackets from urlsplit.hostname
    return ip
