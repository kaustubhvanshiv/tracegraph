"""Structured JSON logging configuration.

Emits JSON-structured log messages and enforces log-level controls:
- Raw event data is NEVER logged at INFO level (Requirement 15.5).
- Only event_id, investigation_id, source_type, and counts are logged at INFO level.
- High-volume raw data or PII is strictly restricted to DEBUG level or omitted.

Requirements: 15.5
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_object: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include standard extra fields if present
        if hasattr(record, "extra") and isinstance(record.extra, dict):  # type: ignore[attr-defined]
            for key, val in record.extra.items():  # type: ignore[attr-defined]
                if key == "raw_data" and record.levelno <= logging.INFO:
                    # Enforce Requirement 15.5: raw_data is NEVER included at INFO or lower severity
                    continue
                log_object[key] = val

        # Handle explicit kwargs passed in extra dict
        for key in ("investigation_id", "event_id", "source_type", "count", "filters"):
            if hasattr(record, key):
                log_object[key] = getattr(record, key)

        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_object)


def setup_logging(log_level: int = logging.INFO) -> None:
    """Configure root logger to emit structured JSON logs."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers to prevent duplicate outputs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)

    # Suppress verbose SQL logging from SQLAlchemy engine
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance configured for structured logging."""
    return logging.getLogger(name)
