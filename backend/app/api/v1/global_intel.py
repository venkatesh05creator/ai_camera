"""Global Intelligence API Endpoints for Universal AI."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from ...core.database import get_db
from .auth import get_current_user
from ...models.entities import User, SavedLocation
from ...services.global_intel_service import (
    get_earthquake_feed,
    get_economic_overview,
    get_live_aviation_tracking,
    get_natural_events,
    get_near_earth_objects,
    get_providers_health,
    get_public_cameras,
    get_unified_map_markers,
    get_weather_intelligence,
)

router = APIRouter(prefix="/global", tags=["Global Intelligence"])


class SavedLocationCreate(BaseModel):
    label: str
    latitude: float
    longitude: float
    radius_km: float = 25.0


@router.get("/config")
def get_map_config(current_user: User = Depends(get_current_user)):
    """Return client-side GIS map configuration and API tokens."""
    carto_key = os.environ.get("CARTO_API_KEY", "").strip() or os.environ.get("MAP_API_KEY", "").strip()
    tile_url = "https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png"
    if carto_key:
        tile_url += f"?key={carto_key}"
    return {
        "carto_api_key": carto_key,
        "default_tile_url": tile_url,
        "attribution": "&copy; OpenStreetMap contributors &copy; CARTO",
    }


@router.get("/map-markers")
def get_map_markers(
    include_disasters: bool = Query(True),
    include_flights: bool = Query(True),
    include_cameras: bool = Query(True),
    include_weather: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve unified map markers across disasters, public cameras, aircraft, and saved locations."""
    # Fetch user's saved locations
    saved_stmt = select(SavedLocation).where(SavedLocation.owner_user_id == current_user.id)
    saved_locs = db.scalars(saved_stmt).all()
    locs_data = [
        {"id": loc.id, "label": loc.label, "latitude": loc.latitude, "longitude": loc.longitude}
        for loc in saved_locs
    ]

    markers = get_unified_map_markers(
        include_disasters=include_disasters,
        include_flights=include_flights,
        include_public_cams=include_cameras,
        include_weather=include_weather,
        user_saved_locations=locs_data,
    )
    return {"markers": markers, "count": len(markers)}


@router.get("/earthquakes")
def get_earthquakes(
    min_magnitude: float = Query(2.5, ge=0.0, le=10.0),
    limit: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Retrieve real-time global earthquake feeds from USGS."""
    quakes = get_earthquake_feed(min_magnitude=min_magnitude, limit=limit)
    return {"earthquakes": quakes, "count": len(quakes)}


@router.get("/weather")
def get_weather(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    location_name: str = Query("Target Area"),
    current_user: User = Depends(get_current_user),
):
    """Retrieve hyper-local weather & conditions via Open-Meteo."""
    return get_weather_intelligence(latitude, longitude, location_name)


@router.get("/aviation")
def get_aviation(
    lat_min: Optional[float] = Query(None),
    lat_max: Optional[float] = Query(None),
    lon_min: Optional[float] = Query(None),
    lon_max: Optional[float] = Query(None),
    limit: int = Query(40, ge=1, le=150),
    current_user: User = Depends(get_current_user),
):
    """Retrieve live aircraft ADS-B telemetry from OpenSky Network."""
    flights = get_live_aviation_tracking(lat_min, lat_max, lon_min, lon_max, limit=limit)
    return {"flights": flights, "count": len(flights)}


@router.get("/economics")
def get_economics(
    current_user: User = Depends(get_current_user),
):
    """Retrieve global forex reference rates, indices, and commodity telemetry."""
    return get_economic_overview()


@router.get("/space/asteroids")
def get_space_asteroids(
    limit: int = Query(15, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Retrieve Near Earth Objects (Asteroid close approaches) via NASA NeoWs."""
    asteroids = get_near_earth_objects(limit=limit)
    return {"asteroids": asteroids, "count": len(asteroids)}


@router.get("/public-cameras")
def get_public_cams(
    current_user: User = Depends(get_current_user),
):
    """Retrieve legitimate open municipal & observatory public webcams."""
    cams = get_public_cameras()
    return {"cameras": cams, "count": len(cams)}


@router.get("/natural-events")
def get_nasa_natural_events(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Retrieve active natural events (wildfires, storms, volcanoes) from NASA EONET."""
    events = get_natural_events(limit=limit)
    return {"events": events, "count": len(events)}


@router.get("/providers")
def get_connected_providers(
    current_user: User = Depends(get_current_user),
):
    """Retrieve health and connectivity status of all integrated global intelligence providers."""
    return {"providers": get_providers_health(), "total_connected": len(get_providers_health())}


@router.get("/saved-locations")
def list_saved_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List owner-saved geographic locations of interest."""
    stmt = select(SavedLocation).where(SavedLocation.owner_user_id == current_user.id)
    locs = db.scalars(stmt).all()
    return [
        {
            "id": l.id,
            "label": l.label,
            "latitude": l.latitude,
            "longitude": l.longitude,
            "radius_km": l.radius_km,
            "created_at": l.created_at.isoformat(),
        }
        for l in locs
    ]


@router.post("/saved-locations", status_code=status.HTTP_201_CREATED)
def create_saved_location(
    payload: SavedLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save a new geographic monitoring point."""
    loc = SavedLocation(
        owner_user_id=current_user.id,
        label=payload.label.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return {
        "id": loc.id,
        "label": loc.label,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "radius_km": loc.radius_km,
    }


@router.delete("/saved-locations/{location_id}")
def delete_saved_location(
    location_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a saved geographic location."""
    stmt = select(SavedLocation).where(
        and_(SavedLocation.id == location_id, SavedLocation.owner_user_id == current_user.id)
    )
    loc = db.scalars(stmt).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Saved location not found")
    db.delete(loc)
    db.commit()
    return {"message": "Location deleted successfully"}

