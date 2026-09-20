from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field, field_validator


class SecurityEvent(BaseModel):
    """Common Security Event Model (normalized representation)."""
    event_id: str = Field(description="Non-empty identifier unique within an investigation")
    source_type: str = Field(description="Parser source type (e.g. sysmon, edr)")
    timestamp: datetime = Field(description="UTC timestamp")
    event_type: str = Field(description="Event classification (e.g. authentication)")
    action: str = Field(description="Action condition (e.g. login, execute, connect, access, auth)")
    user: str | None = Field(default=None, description="Normalized username")
    source_host: str | None = Field(default=None, description="Normalized source hostname")
    destination_host: str | None = Field(default=None, description="Normalized destination hostname")
    source_ip: str | None = Field(default=None, description="Normalized source IP address")
    destination_ip: str | None = Field(default=None, description="Normalized destination IP address")
    process: str | None = Field(default=None, description="Process name or path")
    file: str | None = Field(default=None, description="Absolute file path")
    severity: str | None = Field(default=None, description="Severity: low, medium, high, critical")
    raw_data: dict[str, Any] | None = Field(default=None, description="Original parsed fields preserved")

    @field_validator("event_id")
    @classmethod
    def event_id_must_be_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("event_id must be non-empty")
        return v.strip()

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None:
            v_clean = v.strip().lower()
            if v_clean not in {"low", "medium", "high", "critical"}:
                raise ValueError(f"severity must be one of low/medium/high/critical, got {v!r}")
            return v_clean
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def timestamp_must_be_utc(cls, v: Any) -> Any:
        if isinstance(v, str):
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        elif isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return v

