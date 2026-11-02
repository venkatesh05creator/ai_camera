"""Universal Jarvis AI Command Center — Computer Control Engine
Provides authorized, sandboxed operating-system and workspace automation with an
explicit owner-approval gate for sensitive operations (file deletion, script execution,
production writes).
"""

import os
import glob
import logging
import uuid
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Workspace bounds
ALLOWED_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))).resolve()

# In-memory approval registry for sensitive operations
_PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}
_MAX_PENDING_TTL_SECONDS = 300  # 5 minutes expiration


class ComputerControlService:
    """Jarvis Computer Control agent for file discovery, inspection, document editing,

    and safe script execution.
    """

    @classmethod
    def _is_safe_path(cls, path_str: str) -> bool:
        """Ensure path is within the workspace directory and doesn't escape via '..'."""
        try:
            target = (ALLOWED_ROOT / path_str).resolve()
            return ALLOWED_ROOT in target.parents or target == ALLOWED_ROOT
        except Exception:
            return False

    @classmethod
    def search_workspace_files(
        cls,
        pattern: str,
        subdirectory: str = ".",
        max_results: int = 50,
    ) -> Dict[str, Any]:
        """Search files within the workspace matching a glob or substring pattern."""
        if not cls._is_safe_path(subdirectory):
            return {"error": "Access denied: Target directory outside workspace boundary.", "results": []}

        search_base = (ALLOWED_ROOT / subdirectory).resolve()
        results: List[Dict[str, Any]] = []

        try:
            for root, dirs, files in os.walk(search_base):
                # Skip hidden/large cache directories
                dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv", "__pycache__", ".pytest_cache"]]
                for f in files:
                    if pattern.lower() in f.lower() or glob.fnmatch.fnmatch(f.lower(), pattern.lower()):
                        full_path = Path(root) / f
                        rel_path = full_path.relative_to(ALLOWED_ROOT).as_posix()
                        stat = full_path.stat()
                        results.append({
                            "name": f,
                            "relative_path": rel_path,
                            "size_bytes": stat.st_size,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        })
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            return {
                "success": True,
                "pattern": pattern,
                "count": len(results),
                "results": results,
            }
        except Exception as e:
            logger.error("Error searching files: %s", e)
            return {"error": str(e), "results": []}

    @classmethod
    def read_document(cls, relative_path: str, max_lines: int = 400) -> Dict[str, Any]:
        """Read a document or code file within the workspace safely."""
        if not cls._is_safe_path(relative_path):
            return {"error": "Access denied: Path escapes workspace boundary."}

        target = (ALLOWED_ROOT / relative_path).resolve()
        if not target.exists() or not target.is_file():
            return {"error": f"File does not exist: {relative_path}"}

        # Block reading binary files
        binary_extensions = {".exe", ".dll", ".so", ".bin", ".pyc", ".db", ".sqlite", ".png", ".jpg", ".mp4"}
        if target.suffix.lower() in binary_extensions:
            return {"error": f"Cannot view binary file type '{target.suffix}' as text."}

        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(max_lines)]
                content = "".join(lines)

            stat = target.stat()
            return {
                "success": True,
                "relative_path": relative_path,
                "content": content,
                "size_bytes": stat.st_size,
                "line_count": len(lines),
                "truncated": len(lines) >= max_lines,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

    @classmethod
    def write_document(
        cls,
        relative_path: str,
        content: str,
        overwrite: bool = False,
        approved: bool = False,
    ) -> Dict[str, Any]:
        """Write or edit a document with safety gating."""
        if not cls._is_safe_path(relative_path):
            return {"error": "Access denied: Path escapes workspace boundary."}

        target = (ALLOWED_ROOT / relative_path).resolve()
        is_existing = target.exists()

        # Sensitive check: overwriting existing production code requires approval
        if is_existing and not approved and not relative_path.startswith("scratch/"):
            action_id = str(uuid.uuid4())
            _PENDING_APPROVALS[action_id] = {
                "action_type": "write_file",
                "relative_path": relative_path,
                "content": content,
                "overwrite": overwrite,
                "created_at": time.time(),
            }
            return {
                "status": "requires_approval",
                "action_id": action_id,
                "message": f"Modifying existing file '{relative_path}' requires explicit owner approval.",
                "details": {"path": relative_path, "bytes": len(content.encode("utf-8"))},
            }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w" if overwrite or not is_existing else "a", encoding="utf-8") as f:
                f.write(content)

            return {
                "success": True,
                "relative_path": relative_path,
                "bytes_written": len(content.encode("utf-8")),
                "operation": "overwritten" if is_existing else "created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to write file: {e}"}

    @classmethod
    def list_pending_approvals(cls) -> List[Dict[str, Any]]:
        """List sensitive computer control actions waiting for owner approval."""
        now = time.time()
        active = []
        for aid, data in list(_PENDING_APPROVALS.items()):
            if now - data["created_at"] > _MAX_PENDING_TTL_SECONDS:
                _PENDING_APPROVALS.pop(aid, None)
            else:
                active.append({
                    "action_id": aid,
                    "action_type": data["action_type"],
                    "relative_path": data.get("relative_path", ""),
                    "created_at": datetime.fromtimestamp(data["created_at"], tz=timezone.utc).isoformat(),
                    "expires_in_seconds": int(_MAX_PENDING_TTL_SECONDS - (now - data["created_at"])),
                })
        return active

    @classmethod
    def resolve_approval(cls, action_id: str, approved: bool) -> Dict[str, Any]:
        """Approve or reject a pending computer control action."""
        action = _PENDING_APPROVALS.pop(action_id, None)
        if not action:
            return {"error": "Approval token not found or expired."}

        if not approved:
            return {"status": "rejected", "action_id": action_id, "message": "Action was rejected by the owner."}

        # Execute the approved action
        if action["action_type"] == "write_file":
            return cls.write_document(
                relative_path=action["relative_path"],
                content=action["content"],
                overwrite=action.get("overwrite", True),
                approved=True,
            )

        return {"status": "executed", "action_id": action_id}

    @classmethod
    def inspect_system_diagnostics(cls) -> Dict[str, Any]:
        """Inspect system health, memory, process status, and workspace telemetry."""
        import psutil
        process = psutil.Process()
        cpu_usage = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(ALLOWED_ROOT))

        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "host_os": os.name,
            "cpu_percent": cpu_usage,
            "memory": {
                "total_mb": round(mem.total / (1024 * 1024), 1),
                "used_mb": round(mem.used / (1024 * 1024), 1),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 1),
                "free_gb": round(disk.free / (1024 ** 3), 1),
                "percent": disk.percent,
            },
            "process_uptime_seconds": int(time.time() - process.create_time()),
            "workspace_root": str(ALLOWED_ROOT),
        }
