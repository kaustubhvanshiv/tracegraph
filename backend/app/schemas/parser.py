from typing import Any
from pydantic import BaseModel, Field


class ParsedEvent(BaseModel):
    """Intermediate representation produced by a ParserAdapter before normalization."""
    event_id: str = Field(description="Original event ID preserved unchanged")
    source_type: str = Field(description="Parser source_type classification")
    timestamp_raw: str = Field(description="Raw unparsed timestamp string from log source")
    event_type: str | None = Field(default=None, description="Recognized event category")
    action: str | None = Field(default=None, description="Recognized action condition")
    user: str | None = Field(default=None, description="Raw username field")
    source_host: str | None = Field(default=None, description="Raw source hostname")
    destination_host: str | None = Field(default=None, description="Raw destination hostname")
    source_ip: str | None = Field(default=None, description="Raw source IP address")
    destination_ip: str | None = Field(default=None, description="Raw destination IP address")
    process: str | None = Field(default=None, description="Raw process name or path")
    file: str | None = Field(default=None, description="Raw file path")
    severity: str | None = Field(default=None, description="Raw severity string")
    extra_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Preserves all unrecognized raw event keys without loss"
    )


class ParseError(BaseModel):
    """Returned when a raw event fails parsing; adapters never raise exceptions."""
    event_id: str | None = Field(default=None, description="Event ID if available")
    field_name: str | None = Field(default=None, description="Field causing parsing error if applicable")
    reason: str = Field(description="Human-readable explanation of parse failure")
    raw_event: dict[str, Any] = Field(description="Copy of the raw event dict that failed")
