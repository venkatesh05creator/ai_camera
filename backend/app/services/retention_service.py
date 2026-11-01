"""
backend/app/services/retention_service.py
Automated media & snapshot storage retention cleaner for low-storage environments.

Enforces strict disk boundaries:
- Unreviewed temporary snapshots older than 7 days are automatically purged.
- Ephemeral motion clips older than 30 days are pruned.
- Bounded to the local var/ storage directory; strictly preserves database records.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict

from ..core.config import get_settings

logger = logging.getLogger(__name__)


def clean_directory_by_age(directory: Path, max_age_days: int) -> Dict[str, Any]:
    """Prune files older than max_age_days within a bounded storage directory."""
    if not directory.exists() or not directory.is_dir():
        return {"files_removed": 0, "bytes_reclaimed": 0}

    now = time.time()
    cutoff = now - (max_age_days * 86400.0)
    files_removed = 0
    bytes_reclaimed = 0

    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                try:
                    stat = entry.stat()
                    if stat.st_mtime < cutoff:
                        file_size = stat.st_size
                        os.remove(entry.path)
                        files_removed += 1
                        bytes_reclaimed += file_size
                except Exception as e:
                    logger.debug("Could not remove expired storage file %s: %s", entry.path, e)
    except Exception as exc:
        logger.warning("Error during retention sweep of %s: %s", directory, exc)

    return {
        "files_removed": files_removed,
        "bytes_reclaimed": bytes_reclaimed,
        "mb_reclaimed": round(bytes_reclaimed / (1024 * 1024), 2),
    }


def run_retention_sweep() -> Dict[str, Any]:
    """Execute complete storage-aware retention sweep across snapshots and media directories."""
    settings = get_settings()
    snap_path = Path(settings.snapshot_storage_path)
    media_path = Path(settings.media_storage_path)

    snap_days = getattr(settings, "unreviewed_snapshot_retention_days", 7)
    media_days = getattr(settings, "default_event_retention_days", 30)

    snap_result = clean_directory_by_age(snap_path, snap_days)
    media_result = clean_directory_by_age(media_path, media_days)

    total_mb = round(snap_result["mb_reclaimed"] + media_result["mb_reclaimed"], 2)
    total_files = snap_result["files_removed"] + media_result["files_removed"]

    if total_files > 0:
        logger.info(
            "Storage Retention Sweep completed: %d files pruned, %.2f MB disk space reclaimed.",
            total_files,
            total_mb,
        )

    return {
        "snapshots": snap_result,
        "media": media_result,
        "total_files_removed": total_files,
        "total_mb_reclaimed": total_mb,
    }
