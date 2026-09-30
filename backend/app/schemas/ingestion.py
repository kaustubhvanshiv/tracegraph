"""Ingestion request/response schemas.

Used by:
  - POST /api/investigations/{id}/events
  - POST /api/investigations/{id}/events/batch

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RawEventPayload(BaseModel):
    """Payload for a single raw event submission.

    ``source_type`` identifies the adapter to use; ``raw`` is the
    unprocessed event dict exactly as received from the source.
    """

    source_type: str = Field(description="Registered adapter source_type (e.g. 'siem', 'edr')")
    raw: dict[str, Any] = Field(description="Raw event dict from the originating source")


class RejectedEvent(BaseModel):
    """Details about a single event that failed processing."""

    event_id: str | None = Field(default=None, description="Event ID if available from raw input")
    reason: str = Field(description="Human-readable explanation of the rejection")
    field: str | None = Field(default=None, description="Specific field that caused the failure")


class IngestionResponse(BaseModel):
    """Summary of a completed ingestion run.

    - ``accepted``: number of events that passed all pipeline stages and were persisted
    - ``rejected``: number of events that failed at any stage (parse, normalize, validate)
    - ``errors``:   per-event rejection details (parallel to rejected count)
    """

    accepted: int = Field(description="Number of events successfully processed")
    rejected: int = Field(description="Number of events that failed processing")
    errors: list[RejectedEvent] = Field(
        default_factory=list,
        description="Details for each rejected event",
    )
