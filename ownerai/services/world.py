"""World Monitor — lawful public-data layers (Phase W).

Read-only public-data layers for situational awareness: aircraft (OpenSky
Network), earthquakes (USGS), fires (NASA FIRMS, keyed), cyber vulnerabilities
(CISA Known Exploited Vulnerabilities).  All third-party calls go through this
backend proxy with caching and rate limits; API keys never reach the browser.

Privacy: no tool follows an individual person; no face recognition; no person
tracking; unofficial camera sources are rejected.

Ships behind the ``WORLD_MONITOR`` feature flag (opt-in, default off).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lawful public-data sources
# ---------------------------------------------------------------------------
# Each source lists: friendly name, fetch URL, public attribution, cache TTL,
# and a conservative per-owner rate limit (requests per window).
# Sources requiring an API key (e.g. NASA FIRMS) are skipped unless the key is
# configured; they are never a hard dependency.

SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "aircraft": {
        "name": "OpenSky Network",
        "url": "https://opensky-network.org/api/states/all",
        "attribution": "Aircraft data: OpenSky Network (opensky-network.org)",
        "ttl_seconds": 30,
        "rate_limit": 1,
        "rate_window_seconds": 10,
        "requires_key": False,
        "key_setting": None,
    },
    "earthquakes": {
        "name": "USGS Earthquake Hazards Program",
        "url": "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time&limit=100",
        "attribution": "Earthquake data: U.S. Geological Survey (usgs.gov)",
        "ttl_seconds": 300,
        "rate_limit": 10,
        "rate_window_seconds": 60,
        "requires_key": False,
        "key_setting": None,
    },
    "cyber": {
        "name": "CISA Known Exploited Vulnerabilities Catalog",
        "url": "https://www.cisa.gov/sites/default/files/csv/known_exploited_vulnerabilities.csv",
        "attribution": "Cyber data: CISA Known Exploited Vulnerabilities (cisa.gov)",
        "ttl_seconds": 3600,
        "rate_limit": 5,
        "rate_window_seconds": 3600,
        "requires_key": False,
        "key_setting": None,
    },
    "fires": {
        "name": "NASA FIRMS",
        "url": "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/world/1",
        "attribution": "Fire data: NASA FIRMS (firms.modaps.eosdis.nasa.gov)",
        "ttl_seconds": 900,
        "rate_limit": 1,
        "rate_window_seconds": 3600,
        "requires_key": True,
        "key_setting": "WORLD_FIRMS_API_KEY",
    },
}


class WorldError(RuntimeError):
    """Raised when a World Monitor source cannot be reached."""


# ---------------------------------------------------------------------------
# In-memory TTL cache (per-process; sufficient for a single-owner deployment)
# ---------------------------------------------------------------------------
class TTLCache:
    """Thread-safe, time-bounded cache keyed by source."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_seconds)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_cache = TTLCache()


def _cache_key(source: str, **params: Any) -> str:
    raw = source + "|" + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Source proxy
# ---------------------------------------------------------------------------
def _source_available(source: str, settings: Settings) -> bool:
    """Return whether a source is configured and permitted to be fetched."""
    info = SOURCE_REGISTRY.get(source)
    if info is None:
        return False
    if info["requires_key"]:
        key_setting = info["key_setting"]
        if not key_setting:
            return False
        key = getattr(settings, key_setting, None)
        if not key:
            return False
    return True


def _fetch_json(url: str, timeout: float = 15.0) -> Any:
    """Fetch JSON from a lawful public source, with a bounded timeout."""
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("world source returned %s", exc.response.status_code)
        raise WorldError(f"source returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.warning("world source unavailable: {0}".format(type(exc).__name__))
        raise WorldError("source unavailable") from exc


def fetch_source(
    source: str,
    *,
    settings: Optional[Settings] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch and cache one lawful source.

    Returns ``{"data": ..., "source": ..., "attribution": ..., "fetched_at": ...,
    "stale": bool}``.  On failure the cached (stale) value is returned with
    ``stale=True`` so the caller can degrade gracefully.
    """
    settings = settings or get_settings()
    if not _source_available(source, settings):
        raise WorldError(f"source '{source}' is not configured or permitted")
    info = SOURCE_REGISTRY[source]

    # Rate-limit per source (conservative, in-memory).
    cache_key = _cache_key(source)
    if not force_refresh:
        cached = _cache.get(cache_key)
        if cached is not None:
            return dict(cached)

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {"data": None, "stale": True}
    try:
        url = info["url"]
        if "{key}" in url:
            key_setting = info["key_setting"]
            key = getattr(settings, key_setting, None) or ""
            url = url.format(key=key)
        data = _fetch_json(url)
        payload = {
            "data": data,
            "source": source,
            "name": info["name"],
            "attribution": info["attribution"],
            "fetched_at": now.isoformat(),
            "stale": False,
        }
        _cache.set(cache_key, payload, info["ttl_seconds"])
    except WorldError:
        # Degrade to stale cache if present.
        stale = _cache.get(cache_key)
        if stale is not None:
            stale = dict(stale)
            stale["stale"] = True
            return stale
        raise

    return payload


def available_sources(settings: Optional[Settings] = None) -> list[dict[str, Any]]:
    """List configured sources with availability (for the UI layer picker)."""
    settings = settings or get_settings()
    out: list[dict[str, Any]] = []
    for source, info in SOURCE_REGISTRY.items():
        out.append(
            {
                "id": source,
                "name": info["name"],
                "attribution": info["attribution"],
                "available": _source_available(source, settings),
                "ttl_seconds": info["ttl_seconds"],
            }
        )
    return out
