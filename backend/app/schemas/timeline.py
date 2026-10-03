from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.security_event import SecurityEvent


class TimelineFilter(BaseModel):
    """Filter criteria for timeline events."""
    start_time: datetime | None = None
    end_time: datetime | None = None
    entity_id: str | None = None
    event_type: str | None = None
    source_type: str | None = None
    severity: str | None = None
    limit: int = 100
    offset: int = 0


class TimelineEvent(BaseModel):
    """Timeline event wrapper including cross-linked entity IDs for graph highlight."""
    event: SecurityEvent
    entity_ids: list[str] = Field(default_factory=list, description="Extracted entity IDs for graph cross-linking")


class TimelineResult(BaseModel):
    """Chronologically sorted timeline result."""
    investigation_id: str
    events: list[TimelineEvent] = Field(default_factory=list)
    total: int = 0

