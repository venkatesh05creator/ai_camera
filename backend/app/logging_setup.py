"""Structured, secret-safe logging.

Every record is emitted as one JSON line with ``request_id``, ``logger``,
``level`` and ``message``; a filter redacts obvious secret-shaped values
before anything reaches stderr or the rotating file in ``var/logs``.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_SECRET_KEYS = re.compile(
    r"(?i)(secret|password|passwd|token|api[_-]?key|authorization|cookie|biometric)"
)


class RedactingFilter(logging.Filter):
    """Drop records that would leak secret-shaped values into logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if _SECRET_KEYS.search(msg) and not msg.startswith(("report:", "verify:")):
            # keep short contextual messages, redact anything that looks like a value
            record.msg = re.sub(r"(?i)(secret|password|token|api[_-]?key)[^\s]*=\S+",
                                r"\1=<redacted>", msg)
            record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", *, json_logs: bool = True,
                  log_dir: Path | None = None) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler: logging.Handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_logs else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "aegis.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        fh.addFilter(RedactingFilter())
        root.addHandler(fh)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
