"""Universal Object and Asset Tracking Service.

Tracks registered personal and business assets across camera feeds:
- Vehicles (cars, motorcycles, bicycles)
- Equipment & Tools (laptops, bags, machinery)
- Goods & Packages (shipments, boxes)
- Belongings & Pets

Correlates incoming detection events (object classes, OCR text, camera locations)
with registered assets to maintain continuous situational awareness and last-seen history.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import Session

from ..models.entities import Asset, Camera, DetectionEvent, utcnow

logger = logging.getLogger(__name__)

SUPPORTED_CATEGORIES = ["vehicle", "equipment", "goods", "personal_item", "pet"]
SUPPORTED_METHODS = ["visual", "plate", "barcode", "rfid", "manual"]


def register_asset(
    db: Session,
    owner_user_id: str,
    name: str,
    category: str = "vehicle",
    tracking_method: str = "visual",
    identifier: Optional[str] = None,
    location_label: str = "Home Garage",
    camera_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Asset:
    """Register a new asset into the owner's personal inventory."""
    clean_cat = category.lower().strip()
    if clean_cat not in SUPPORTED_CATEGORIES:
        clean_cat = "vehicle"

    clean_method = tracking_method.lower().strip()
    if clean_method not in SUPPORTED_METHODS:
        clean_method = "visual"

    asset = Asset(
        owner_user_id=owner_user_id,
        name=name.strip(),
        category=clean_cat,
        tracking_method=clean_method,
        identifier=(identifier or "").strip() or None,
        location_label=location_label.strip(),
        camera_id=camera_id,
        status="stationary",
        last_seen_at=utcnow(),
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_user_assets(
    db: Session,
    owner_user_id: str,
    category: Optional[str] = None,
) -> List[Asset]:
    """Retrieve all registered assets for an owner."""
    query = select(Asset).where(Asset.owner_user_id == owner_user_id)
    if category:
        query = query.where(Asset.category == category.lower().strip())
    query = query.order_by(desc(Asset.created_at))
    return list(db.scalars(query).all())


def get_asset_by_id(db: Session, owner_user_id: str, asset_id: str) -> Optional[Asset]:
    """Retrieve an asset by ID verifying ownership."""
    stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.owner_user_id == owner_user_id))
    return db.scalars(stmt).first()


def update_asset(
    db: Session,
    owner_user_id: str,
    asset_id: str,
    **kwargs: Any,
) -> Optional[Asset]:
    """Update asset attributes."""
    asset = get_asset_by_id(db, owner_user_id, asset_id)
    if not asset:
        return None

    for field, val in kwargs.items():
        if hasattr(asset, field) and val is not None:
            if field == "metadata_json" and isinstance(val, dict):
                setattr(asset, field, json.dumps(val))
            else:
                setattr(asset, field, val)

    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, owner_user_id: str, asset_id: str) -> bool:
    """Remove an asset from inventory."""
    asset = get_asset_by_id(db, owner_user_id, asset_id)
    if not asset:
        return False
    db.delete(asset)
    db.commit()
    return True


def correlate_event_with_assets(
    db: Session,
    owner_user_id: str,
    camera_id: str,
    detected_classes: List[str],
    ocr_texts: Optional[List[str]] = None,
    location_label: str = "",
) -> List[Dict[str, Any]]:
    """Match a camera detection event against owner's registered assets and update status.
    
    Returns list of matched asset updates.
    """
    assets = get_user_assets(db, owner_user_id)
    if not assets:
        return []

    matched: List[Dict[str, Any]] = []
    classes_lower = {c.lower() for c in detected_classes}
    ocr_tokens = {t.lower().strip() for t in (ocr_texts or []) if t}

    for asset in assets:
        is_match = False
        match_reason = ""

        # Category visual mapping
        if asset.category == "vehicle" and any(v in classes_lower for v in ["car", "truck", "bus", "motorcycle", "vehicle"]):
            # Check if identifier matches OCR or if it's the only vehicle
            if asset.identifier:
                id_clean = asset.identifier.lower().replace("-", "").replace(" ", "")
                for token in ocr_tokens:
                    token_clean = token.replace("-", "").replace(" ", "")
                    if id_clean in token_clean or token_clean in id_clean:
                        is_match = True
                        match_reason = f"Plate/Text match: {token}"
                        break
            else:
                is_match = True
                match_reason = "Vehicle visual class match"

        elif asset.category == "equipment" and any(e in classes_lower for e in ["laptop", "backpack", "suitcase", "cell phone"]):
            is_match = True
            match_reason = f"Equipment visual detection"

        elif asset.category == "pet" and any(p in classes_lower for p in ["dog", "cat", "bird"]):
            is_match = True
            match_reason = f"Pet visual detection"

        if is_match:
            asset.last_seen_at = utcnow()
            asset.camera_id = camera_id
            if location_label:
                asset.location_label = location_label
            asset.status = "active"
            matched.append({
                "asset_id": asset.id,
                "asset_name": asset.name,
                "category": asset.category,
                "match_reason": match_reason,
                "location": asset.location_label,
            })

    if matched:
        db.commit()

    return matched


def get_asset_summary(db: Session, owner_user_id: str) -> Dict[str, Any]:
    """Provide high-level inventory and tracking status summary."""
    assets = get_user_assets(db, owner_user_id)
    summary = {
        "total_assets": len(assets),
        "by_category": {},
        "by_status": {"active": 0, "stationary": 0, "missing": 0, "in_transit": 0},
        "recent_sightings": [],
    }

    for a in assets:
        cat = a.category
        summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
        stat = a.status if a.status in summary["by_status"] else "active"
        summary["by_status"][stat] += 1

        if a.last_seen_at:
            summary["recent_sightings"].append({
                "id": a.id,
                "name": a.name,
                "category": a.category,
                "location": a.location_label,
                "status": a.status,
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
            })

    # Sort recent sightings by timestamp
    summary["recent_sightings"].sort(key=lambda x: x["last_seen_at"] or "", reverse=True)
    summary["recent_sightings"] = summary["recent_sightings"][:10]
    return summary

