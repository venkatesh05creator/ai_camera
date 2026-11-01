"""Universal Asset and Object Tracking API Endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.database import get_db
from .auth import get_current_user
from ...models.entities import User
from ...services.asset_tracking_service import (
    delete_asset,
    get_asset_by_id,
    get_asset_summary,
    get_user_assets,
    register_asset,
    update_asset,
)

router = APIRouter(prefix="/assets", tags=["Asset Tracking"])


class AssetCreate(BaseModel):
    name: str
    category: str = "vehicle"
    tracking_method: str = "visual"
    identifier: Optional[str] = None
    location_label: str = "Home Area"
    camera_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    tracking_method: Optional[str] = None
    identifier: Optional[str] = None
    status: Optional[str] = None
    location_label: Optional[str] = None
    camera_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def _format_asset(a) -> Dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "category": a.category,
        "tracking_method": a.tracking_method,
        "identifier": a.identifier,
        "status": a.status,
        "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
        "location_label": a.location_label,
        "camera_id": a.camera_id,
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
def list_assets(
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all registered personal assets with optional category filtering."""
    assets = get_user_assets(db, current_user.id, category)
    return [_format_asset(a) for a in assets]


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get high-level asset inventory statistics and recent camera sightings."""
    return get_asset_summary(db, current_user.id)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Register a new asset into personal surveillance inventory."""
    asset = register_asset(
        db=db,
        owner_user_id=current_user.id,
        name=payload.name,
        category=payload.category,
        tracking_method=payload.tracking_method,
        identifier=payload.identifier,
        location_label=payload.location_label,
        camera_id=payload.camera_id,
        metadata=payload.metadata,
    )
    return _format_asset(asset)


@router.get("/{asset_id}")
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details for a specific asset."""
    asset = get_asset_by_id(db, current_user.id, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _format_asset(asset)


@router.patch("/{asset_id}")
def patch_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update asset metadata or status."""
    updates = payload.model_dump(exclude_unset=True)
    if "metadata" in updates:
        updates["metadata_json"] = updates.pop("metadata")
    asset = update_asset(db, current_user.id, asset_id, **updates)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _format_asset(asset)


@router.delete("/{asset_id}")
def remove_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an asset from the inventory."""
    ok = delete_asset(db, current_user.id, asset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"message": "Asset deleted successfully"}

