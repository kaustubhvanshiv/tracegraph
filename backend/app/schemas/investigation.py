from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class InvestigationStatus(str, Enum):
    """Investigation lifecycle statuses."""
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    CLOSED = "CLOSED"


class InvestigationOutcome(str, Enum):
    """Allowed investigation outcome labels."""
    TRUE_POSITIVE = "TRUE_POSITIVE"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    ESCALATED = "ESCALATED"


class Investigation(BaseModel):
    """Investigation metadata schema."""
    investigation_id: str
    title: str
    description: str | None = None
    status: InvestigationStatus = InvestigationStatus.OPEN
    outcome: str | None = None
    created_at: datetime
    updated_at: datetime
    owner_id: str
    event_count: int = 0


class CreateInvestigationPayload(BaseModel):
    """Payload for creating a new investigation."""
    title: str = Field(min_length=1, description="Investigation title")
    description: str | None = None


class OutcomePayload(BaseModel):
    """Payload for recording investigation outcome."""
    outcome: str = Field(description="Outcome classification: TRUE_POSITIVE, FALSE_POSITIVE, INCONCLUSIVE, ESCALATED")

    @field_validator("outcome")
    @classmethod
    def outcome_must_be_valid(cls, v: str) -> str:
        valid_outcomes = {o.value for o in InvestigationOutcome}
        if v not in valid_outcomes:
            raise ValueError(f"outcome must be one of {sorted(valid_outcomes)}, got {v!r}")
        return v


class NotePayload(BaseModel):
    """Payload for creating an analyst note."""
    body: str = Field(min_length=1, description="Note body text")


class Note(BaseModel):
    """Analyst note schema."""
    note_id: str
    investigation_id: str
    author_id: str
    body: str
    created_at: datetime


class InvestigationFilter(BaseModel):
    """Filter parameters for listing investigations."""
    status: InvestigationStatus | None = None
    owner_id: str | None = None
    limit: int = 50
    offset: int = 0

