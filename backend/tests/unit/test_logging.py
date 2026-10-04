"""Unit tests for JSON structured logging (Task 21).

Tests:
  - JSON output structure
  - Raw event data filtering at INFO level (Requirement 15.5)
  - Extra attribute inclusion for event_id and investigation_id
"""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from app.core.logging import JSONFormatter


def test_json_formatter_structure() -> None:
    formatter = JSONFormatter()
    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test.py",
        lno=10,
        msg="Test log message",
        args=(),
        exc_info=None,
    )
    record.investigation_id = "inv-100"  # type: ignore[attr-defined]
    record.event_id = "evt-001"  # type: ignore[attr-defined]

    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test log message"
    assert data["investigation_id"] == "inv-100"
    assert data["event_id"] == "evt-001"
    assert "timestamp" in data


def test_json_formatter_filters_raw_data_at_info_level() -> None:
    formatter = JSONFormatter()
    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test.py",
        lno=15,
        msg="Event processed",
        args=(),
        exc_info=None,
    )
    record.extra = {"raw_data": {"secret_password": "123", "sensitive_payload": "PII"}}  # type: ignore[attr-defined]

    output = formatter.format(record)
    data = json.loads(output)

    # Raw data must NOT be present at INFO level (Requirement 15.5)
    assert "raw_data" not in data
    assert "secret_password" not in output
