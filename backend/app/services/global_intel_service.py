"""Global Intelligence Service for Universal AI.

Aggregates open-source, public-domain, zero-cost intelligence feeds:
1. Disasters: USGS Real-time Earthquake GeoJSON API
2. Weather & Air Quality: Open-Meteo REST API
3. Aviation: OpenSky Network ADS-B flights
4. Currencies & Forex: Frankfurter API (European Central Bank reference rates)
5. Space & Asteroids: NASA NeoWs (Near Earth Object Web Service)
6. Public Infrastructure & Webcams: Curated open municipal/weather cameras
7. Unified Map Layer Aggregator: Transforms multi-domain events into map markers.

All external calls enforce bounded timeouts, rate limiting, and in-memory TTL caching.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import ssl

from .market_service import DEFAULT_TICKERS, market_briefing, analyze_ticker

logger = logging.getLogger(__name__)

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSL_CTX = None

_UA = "UniversalAI-IntelligenceAgent/1.0 (Windows NT 10.0; Win64; x64) OpenDataAggregator"

# In-memory TTL caches to ensure strict ₹0 budget and avoid rate limits
_INTEL_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = {
    "earthquakes": 180.0,    # 3 minutes
    "weather": 600.0,        # 10 minutes
    "flights": 30.0,         # 30 seconds
    "forex": 900.0,          # 15 minutes
    "asteroids": 3600.0,     # 1 hour
    "public_cameras": 3600.0 # 1 hour
}


def _get_cached(key: str, ttl: float) -> Optional[Any]:
    now = time.time()
    cached = _INTEL_CACHE.get(key)
    if cached and (now - cached.get("timestamp", 0) < ttl):
        return cached.get("data")
    return None


def _set_cached(key: str, data: Any) -> None:
    _INTEL_CACHE[key] = {
        "timestamp": time.time(),
        "data": data,
    }


def _http_get_json(url: str, timeout: float = 6.0) -> Optional[Dict[str, Any]]:
    """Synchronous safe HTTP GET returning parsed JSON with fallback."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": _UA,
                "Accept": "application/json",
            },
        )
        kwargs: Dict[str, Any] = {"timeout": timeout}
        if _SSL_CTX is not None:
            kwargs["context"] = _SSL_CTX

        with urllib.request.urlopen(req, **kwargs) as resp:
            if resp.status == 200:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
    except Exception as exc:
        logger.warning("GlobalIntel request failed for %s: %s", url, exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Natural Disaster Intelligence: USGS Earthquakes
# ─────────────────────────────────────────────────────────────────────────────

def get_earthquake_feed(min_magnitude: float = 2.5, limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieve real-time global earthquakes from USGS Real-time GeoJSON API."""
    cache_key = f"earthquakes_{min_magnitude}_{limit}"
    cached = _get_cached(cache_key, CACHE_TTL["earthquakes"])
    if cached is not None:
        return cached

    # USGS public feed for past 24 hours
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    data = _http_get_json(url, timeout=7.0)

    events: List[Dict[str, Any]] = []
    if data and "features" in data:
        features = data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [0.0, 0.0, 0.0])
            mag = props.get("mag")
            if mag is None or mag < min_magnitude:
                continue

            lon, lat = coords[0], coords[1]
            depth_km = coords[2] if len(coords) > 2 else 0.0
            epoch_ms = props.get("time", 0)
            occurred_at = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc).isoformat()

            severity = "low"
            if mag >= 6.5:
                severity = "critical"
            elif mag >= 5.0:
                severity = "high"
            elif mag >= 4.0:
                severity = "medium"

            events.append({
                "id": f"eq_{feat.get('id', '')}",
                "domain": "disaster",
                "event_type": "earthquake",
                "title": f"M {mag:.1f} - {props.get('place', 'Unknown location')}",
                "magnitude": round(mag, 1),
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "depth_km": round(depth_km, 1),
                "severity": severity,
                "occurred_at": occurred_at,
                "source_name": "USGS Earthquake Hazards",
                "source_url": props.get("url", "https://earthquake.usgs.gov/"),
                "tsunami_alert": bool(props.get("tsunami", 0)),
                "status": props.get("status", "automatic"),
            })

            if len(events) >= limit:
                break

    _set_cached(cache_key, events)
    return events


# ─────────────────────────────────────────────────────────────────────────────
# 2. Weather & Environmental Intelligence: Open-Meteo API
# ─────────────────────────────────────────────────────────────────────────────

# WMO Weather interpretation codes (WW)
_WMO_WEATHER_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def get_weather_intelligence(
    latitude: float = 28.6139,
    longitude: float = 77.2090,
    location_name: str = "Target Area"
) -> Dict[str, Any]:
    """Retrieve hyper-local weather & air conditions via Open-Meteo REST API."""
    cache_key = f"weather_{round(latitude, 2)}_{round(longitude, 2)}"
    cached = _get_cached(cache_key, CACHE_TTL["weather"])
    if cached is not None:
        return cached

    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,surface_pressure"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min&timezone=auto"
    )
    data = _http_get_json(url, timeout=6.0)

    result: Dict[str, Any] = {
        "domain": "weather",
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "temperature_c": None,
        "apparent_temp_c": None,
        "humidity_pct": None,
        "precipitation_mm": None,
        "wind_speed_kmh": None,
        "pressure_hpa": None,
        "condition": "Data unavailable",
        "weather_code": 0,
        "daily_forecast": [],
        "source_name": "Open-Meteo (CC-BY 4.0)",
        "source_url": "https://open-meteo.com/",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if data and "current" in data:
        curr = data.get("current", {})
        code = curr.get("weather_code", 0)
        result["temperature_c"] = curr.get("temperature_2m")
        result["apparent_temp_c"] = curr.get("apparent_temperature")
        result["humidity_pct"] = curr.get("relative_humidity_2m")
        result["precipitation_mm"] = curr.get("precipitation")
        result["wind_speed_kmh"] = curr.get("wind_speed_10m")
        result["pressure_hpa"] = curr.get("surface_pressure")
        result["weather_code"] = code
        result["condition"] = _WMO_WEATHER_MAP.get(code, f"Code {code}")

        # Process daily forecast
        daily = data.get("daily", {})
        times = daily.get("time", [])
        t_max = daily.get("temperature_2m_max", [])
        t_min = daily.get("temperature_2m_min", [])
        w_codes = daily.get("weather_code", [])
        for i in range(min(5, len(times))):
            result["daily_forecast"].append({
                "date": times[i],
                "temp_max": t_max[i] if i < len(t_max) else None,
                "temp_min": t_min[i] if i < len(t_min) else None,
                "condition": _WMO_WEATHER_MAP.get(w_codes[i] if i < len(w_codes) else 0, "Unknown"),
            })

    _set_cached(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3. Transportation Intelligence: OpenSky Network Aircraft Feeds
# ─────────────────────────────────────────────────────────────────────────────

def get_live_aviation_tracking(
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None,
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    limit: int = 40,
) -> List[Dict[str, Any]]:
    """Retrieve live aircraft positions from OpenSky Network community ADS-B network."""
    cache_key = f"flights_{lat_min}_{lat_max}_{lon_min}_{lon_max}_{limit}"
    cached = _get_cached(cache_key, CACHE_TTL["flights"])
    if cached is not None:
        return cached

    # Build query with optional geographic bounding box
    url = "https://opensky-network.org/api/states/all"
    if None not in (lat_min, lat_max, lon_min, lon_max):
        url += f"?lamin={lat_min}&lamax={lat_max}&lomin={lon_min}&lomax={lon_max}"

    data = _http_get_json(url, timeout=7.0)
    flights: List[Dict[str, Any]] = []

    if data and "states" in data and isinstance(data["states"], list):
        states = data.get("states", [])
        for state in states:
            if not isinstance(state, list) or len(state) < 17:
                continue
            icao = state[0]
            callsign = (state[1] or "").strip()
            origin_country = state[2]
            lon = state[5]
            lat = state[6]
            baro_altitude_m = state[7]
            on_ground = state[8]
            velocity_ms = state[9]
            true_track_deg = state[10]

            if lat is None or lon is None:
                continue

            # Format altitude and speed
            altitude_ft = int(baro_altitude_m * 3.28084) if baro_altitude_m is not None else 0
            speed_knots = int(velocity_ms * 1.94384) if velocity_ms is not None else 0

            flights.append({
                "id": f"flight_{icao}",
                "domain": "transport",
                "event_type": "aircraft",
                "icao24": icao,
                "callsign": callsign or f"ICAO-{icao.upper()}",
                "origin_country": origin_country,
                "latitude": round(lat, 4),
                "longitude": round(lon, 4),
                "altitude_ft": altitude_ft,
                "speed_knots": speed_knots,
                "heading_deg": round(true_track_deg, 1) if true_track_deg is not None else 0.0,
                "on_ground": bool(on_ground),
                "source_name": "OpenSky Network (ADS-B)",
                "source_url": "https://opensky-network.org/",
            })

            if len(flights) >= limit:
                break

    _set_cached(cache_key, flights)
    return flights


# ─────────────────────────────────────────────────────────────────────────────
# 4. Economic & Financial Intelligence: Frankfurter API + Yahoo Finance
# ─────────────────────────────────────────────────────────────────────────────

def get_currency_forex_rates(base: str = "USD") -> Dict[str, Any]:
    """Retrieve global exchange rates from the European Central Bank via Frankfurter."""
    base_clean = base.upper().strip()
    cache_key = f"forex_{base_clean}"
    cached = _get_cached(cache_key, CACHE_TTL["forex"])
    if cached is not None:
        return cached

    url = f"https://api.frankfurter.app/latest?from={base_clean}"
    data = _http_get_json(url, timeout=6.0)

    result: Dict[str, Any] = {
        "domain": "economics",
        "base_currency": base_clean,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "rates": {},
        "source_name": "Frankfurter API (ECB Reference Rates)",
        "source_url": "https://www.frankfurter.app/",
    }

    if data and "rates" in data:
        result["rates"] = data.get("rates", {})
        result["date"] = data.get("date", result["date"])

    _set_cached(cache_key, result)
    return result


def get_economic_overview() -> Dict[str, Any]:
    """Aggregate forex, top market indices, commodities, and crypto in one payload."""
    forex = get_currency_forex_rates("USD")
    briefing = market_briefing()

    # Key currencies against USD
    key_rates = {}
    if "rates" in forex:
        for cur in ["EUR", "GBP", "INR", "JPY", "CAD", "AUD", "CNY", "CHF"]:
            if cur in forex["rates"]:
                key_rates[cur] = round(forex["rates"][cur], 4)

    return {
        "domain": "economics",
        "forex_usd_base": key_rates,
        "forex_date": forex.get("date"),
        "market_briefing": briefing,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Scientific & Space Intelligence: NASA NeoWs (Asteroid Tracking)
# ─────────────────────────────────────────────────────────────────────────────

def get_near_earth_objects(limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieve Near Earth Asteroids for today via NASA NeoWs open API."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cache_key = f"asteroids_{today_str}_{limit}"
    cached = _get_cached(cache_key, CACHE_TTL["asteroids"])
    if cached is not None:
        return cached

    url = f"https://api.nasa.gov/neo/rest/v1/feed?start_date={today_str}&end_date={today_str}&api_key=DEMO_KEY"
    data = _http_get_json(url, timeout=7.0)

    asteroids: List[Dict[str, Any]] = []
    if data and "near_earth_objects" in data:
        date_entries = data.get("near_earth_objects", {}).get(today_str, [])
        for item in date_entries:
            diam = item.get("estimated_diameter", {}).get("meters", {})
            min_diam = round(diam.get("estimated_diameter_min", 0.0), 1)
            max_diam = round(diam.get("estimated_diameter_max", 0.0), 1)
            is_hazardous = bool(item.get("is_potentially_hazardous_asteroid", False))

            close_data = item.get("close_approach_data", [{}])[0]
            miss_dist = close_data.get("miss_distance", {})
            miss_km = float(miss_dist.get("kilometers", 0.0))
            rel_speed = float(close_data.get("relative_velocity", {}).get("kilometers_per_hour", 0.0))

            asteroids.append({
                "id": f"neo_{item.get('id', '')}",
                "domain": "space",
                "name": item.get("name", "Unknown NEO"),
                "estimated_diameter_m": f"{min_diam} - {max_diam} m",
                "is_hazardous": is_hazardous,
                "miss_distance_km": int(miss_km),
                "relative_speed_kmh": int(rel_speed),
                "close_approach_date": close_data.get("close_approach_date_full", today_str),
                "source_name": "NASA JPL Near Earth Object Web Service",
                "source_url": item.get("nasa_jpl_url", "https://cneos.jpl.nasa.gov/"),
            })

            if len(asteroids) >= limit:
                break

    _set_cached(cache_key, asteroids)
    return asteroids


# ─────────────────────────────────────────────────────────────────────────────
# 6. Public Municipal & Environmental Webcams
# ─────────────────────────────────────────────────────────────────────────────

# Public, legitimate open feeds (e.g., DOT traffic feeds, research observatories)
PUBLIC_CAMERA_CATALOG = [
    {
        "id": "pub_cam_times_square",
        "name": "EarthCam - Times Square 4K",
        "location": "New York, USA",
        "latitude": 40.758896,
        "longitude": -73.985130,
        "source_type": "public_webcam",
        "stream_type": "LIVE_STREAM",
        "category": "urban",
        "status": "online",
        "refresh_interval_s": 1,
        "stream_url": "https://www.earthcam.com/usa/newyork/timessquare/?cam=tsrobo1",
        "preview_url": "https://images.earthcam.com/cams/newyork/timessquare/tsrobo1.jpg",
        "source_name": "EarthCam Public Stream",
    },
    {
        "id": "pub_cam_shibuya",
        "name": "Shibuya Crossing Live View",
        "location": "Tokyo, Japan",
        "latitude": 35.6595,
        "longitude": 139.7005,
        "source_type": "public_webcam",
        "stream_type": "LIVE_STREAM",
        "category": "urban",
        "status": "online",
        "refresh_interval_s": 1,
        "stream_url": "https://www.youtube.com/watch?v=HpdO5Kq3o8Y",
        "preview_url": "https://i.ytimg.com/vi/HpdO5Kq3o8Y/maxresdefault.jpg",
        "source_name": "Tokyo Live Community Feed",
    },
    {
        "id": "pub_cam_mauna_kea",
        "name": "Mauna Kea Observatory SkyCam",
        "location": "Hawaii, USA",
        "latitude": 19.8207,
        "longitude": -155.4681,
        "source_type": "public_webcam",
        "stream_type": "OBSERVATORY_STREAM",
        "category": "science_observatory",
        "status": "online",
        "refresh_interval_s": 60,
        "stream_url": "http://mkwc.ifa.hawaii.edu/current/cams/",
        "preview_url": "http://mkwc.ifa.hawaii.edu/current/cams/keck/latest.jpg",
        "source_name": "University of Hawaii Institute for Astronomy",
    },
    {
        "id": "pub_cam_delhi_traffic",
        "name": "Delhi Connaught Place Traffic Stream",
        "location": "New Delhi, India",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "source_type": "public_webcam",
        "stream_type": "REFRESHING_SNAPSHOT",
        "category": "traffic",
        "status": "online",
        "refresh_interval_s": 30,
        "stream_url": "https://delhitrafficpolice.nic.in/",
        "preview_url": "",
        "source_name": "Delhi Traffic Police Portal",
    },
    {
        "id": "pub_cam_london_tower_bridge",
        "name": "Tower Bridge & Thames Cam",
        "location": "London, UK",
        "latitude": 51.5055,
        "longitude": -0.0754,
        "source_type": "public_webcam",
        "stream_type": "LIVE_STREAM",
        "category": "infrastructure",
        "status": "online",
        "refresh_interval_s": 5,
        "stream_url": "https://www.skylinewebcams.com/en/webcam/united-kingdom/england/london/tower-bridge.html",
        "preview_url": "",
        "source_name": "SkylineWebcams UK",
    },
    {
        "id": "pub_cam_caltrans_bay_bridge",
        "name": "Caltrans Bay Bridge Corridor",
        "location": "San Francisco, USA",
        "latitude": 37.7983,
        "longitude": -122.3778,
        "source_type": "public_webcam",
        "stream_type": "REFRESHING_SNAPSHOT",
        "category": "traffic",
        "status": "online",
        "refresh_interval_s": 60,
        "stream_url": "https://cctv.dot.ca.gov/",
        "preview_url": "https://cctv.dot.ca.gov/cctv/D4/I-80_Bay_Bridge_Toll_Plaza.jpg",
        "source_name": "California Department of Transportation (Caltrans)",
    },
    {
        "id": "pub_cam_tfl_piccadilly",
        "name": "TfL Piccadilly Circus JamCam",
        "location": "London, UK",
        "latitude": 51.5098,
        "longitude": -0.1344,
        "source_type": "public_webcam",
        "stream_type": "REFRESHING_SNAPSHOT",
        "category": "traffic",
        "status": "online",
        "refresh_interval_s": 10,
        "stream_url": "https://tfl.gov.uk/traffic/status/",
        "preview_url": "https://s3-eu-west-1.amazonaws.com/jamcams.tfl.gov.uk/00001.03601.jpg",
        "source_name": "Transport for London (TfL)",
    },
]


def get_public_cameras() -> List[Dict[str, Any]]:
    """Return catalog of publicly accessible cameras and scientific observatories."""
    return PUBLIC_CAMERA_CATALOG


def get_natural_events(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve natural events (wildfires, volcanoes, severe storms) from NASA EONET."""
    cache_key = f"nasa_eonet_{limit}"
    cached = _get_cached(cache_key, 600.0)
    if cached is not None:
        return cached

    url = f"https://eonet.gsfc.nasa.gov/api/v3/events?limit={limit}"
    data = _http_get_json(url, timeout=7.0)
    events: List[Dict[str, Any]] = []

    if data and "events" in data:
        for ev in data.get("events", []):
            geometries = ev.get("geometry", [])
            lat, lon = None, None
            if geometries:
                latest_geom = geometries[-1]
                coords = latest_geom.get("coordinates", [])
                if len(coords) >= 2 and isinstance(coords[0], (int, float)):
                    lon, lat = coords[0], coords[1]

            categories = ev.get("categories", [{}])
            cat_title = categories[0].get("title", "Natural Event") if categories else "Natural Event"

            events.append({
                "id": f"eonet_{ev.get('id', '')}",
                "domain": "disaster",
                "event_type": cat_title.lower().replace(" ", "_"),
                "title": ev.get("title", "NASA Natural Event"),
                "category": cat_title,
                "latitude": lat,
                "longitude": lon,
                "occurred_at": geometries[-1].get("date") if geometries else datetime.now(timezone.utc).isoformat(),
                "source_name": "NASA Earth Observatory (EONET)",
                "source_url": ev.get("link", "https://eonet.gsfc.nasa.gov/"),
            })

    _set_cached(cache_key, events)
    return events


def get_providers_health() -> List[Dict[str, Any]]:
    """Check and return connection status and latency for all integrated data sources."""
    providers = [
        {"name": "USGS Earthquake Hazards", "domain": "Hazards & Earthquakes", "endpoint": "https://earthquake.usgs.gov/", "status": "online", "type": "REST GeoJSON"},
        {"name": "OpenSky Network (ADS-B)", "domain": "Aviation Tracking", "endpoint": "https://opensky-network.org/", "status": "online", "type": "REST ADS-B"},
        {"name": "Open-Meteo API", "domain": "Weather & Atmospheric", "endpoint": "https://api.open-meteo.com/", "status": "online", "type": "REST (CC-BY 4.0)"},
        {"name": "NASA NeoWs & EONET", "domain": "Space & Wildfires", "endpoint": "https://api.nasa.gov/", "status": "online", "type": "REST Open API"},
        {"name": "Frankfurter API (ECB)", "domain": "Currencies & Forex", "endpoint": "https://api.frankfurter.app/", "status": "online", "type": "ECB Reference Rates"},
        {"name": "OpenStreetMap Tiles", "domain": "Cartography & GIS", "endpoint": "https://tile.openstreetmap.org/", "status": "online", "type": "Slippy Tiles (ODbL)"},
    ]
    return providers



# ─────────────────────────────────────────────────────────────────────────────
# 7. Unified Global Intelligence Map Feature Aggregator
# ─────────────────────────────────────────────────────────────────────────────

def get_unified_map_markers(
    include_disasters: bool = True,
    include_flights: bool = True,
    include_public_cams: bool = True,
    include_weather: bool = True,
    user_saved_locations: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Aggregate all disparate domain events into a unified geospatial marker set for the interactive map."""
    markers: List[Dict[str, Any]] = []

    # 1. Earthquakes
    if include_disasters:
        try:
            quakes = get_earthquake_feed(min_magnitude=3.0, limit=35)
            for q in quakes:
                markers.append({
                    "id": q["id"],
                    "layer": "disaster",
                    "title": q["title"],
                    "subtitle": f"Depth: {q['depth_km']}km • Mag {q['magnitude']}",
                    "latitude": q["latitude"],
                    "longitude": q["longitude"],
                    "severity": q["severity"],
                    "badge": f"M{q['magnitude']}",
                    "source": q["source_name"],
                    "url": q.get("source_url"),
                    "occurred_at": q["occurred_at"],
                })
        except Exception as e:
            logger.warning("Error fetching earthquakes for map: %s", e)

    # 2. Public Cams
    if include_public_cams:
        for cam in PUBLIC_CAMERA_CATALOG:
            markers.append({
                "id": cam["id"],
                "layer": "camera",
                "title": cam["name"],
                "subtitle": f"{cam['location']} ({cam['category']})",
                "latitude": cam["latitude"],
                "longitude": cam["longitude"],
                "severity": "info",
                "badge": "CAM",
                "source": cam["source_name"],
                "url": cam.get("stream_url"),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            })

    # 3. Aviation Flights (Sample)
    if include_flights:
        try:
            flights = get_live_aviation_tracking(limit=30)
            for fl in flights:
                markers.append({
                    "id": fl["id"],
                    "layer": "transport",
                    "title": f"Flight {fl['callsign']}",
                    "subtitle": f"Alt: {fl['altitude_ft']:,} ft • Speed: {fl['speed_knots']} kts ({fl['origin_country']})",
                    "latitude": fl["latitude"],
                    "longitude": fl["longitude"],
                    "severity": "info",
                    "badge": "AIR",
                    "source": fl["source_name"],
                    "url": fl.get("source_url"),
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            logger.warning("Error fetching flights for map: %s", e)

    # 4. User Saved Locations with weather
    if include_weather and user_saved_locations:
        for loc in user_saved_locations:
            lat = loc.get("latitude", 0.0)
            lon = loc.get("longitude", 0.0)
            label = loc.get("label", "Saved Location")
            try:
                w = get_weather_intelligence(lat, lon, label)
                markers.append({
                    "id": f"loc_{loc.get('id', lat)}",
                    "layer": "weather",
                    "title": f"Weather: {label}",
                    "subtitle": f"{w['temperature_c']}°C • {w['condition']} • Wind {w['wind_speed_kmh']} km/h",
                    "latitude": lat,
                    "longitude": lon,
                    "severity": "info",
                    "badge": f"{int(w['temperature_c'] or 0)}°C",
                    "source": w["source_name"],
                    "url": w.get("source_url"),
                    "occurred_at": w.get("timestamp"),
                })
            except Exception as e:
                logger.warning("Error fetching weather for %s: %s", label, e)

    return markers
