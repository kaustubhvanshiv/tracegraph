from typing import Any
from pydantic import BaseModel, Field
from app.schemas.entity import Entity
from app.schemas.relationship import CorrelatedRelationship
from app.schemas.security_event import SecurityEvent


class EvidenceDetail(BaseModel):
    """Full evidence record for a single event."""
    event: SecurityEvent
    raw_data: dict[str, Any] | None = None
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[CorrelatedRelationship] = Field(default_factory=list)
    correlation_metadata: list[dict[str, Any]] = Field(default_factory=list)


class InvestigationContext(BaseModel):
    """Bounded structured context for AI Summary generation."""
    investigation_id: str
    total_events: int
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[CorrelatedRelationship] = Field(default_factory=list)
    sampled_events: list[SecurityEvent] = Field(default_factory=list)


class SummaryResult(BaseModel):
    """Grounded AI-generated narrative summary."""
    overview: str = ""
    chronological_sequence: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    key_relationships: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list, description="Event IDs from context cited as evidence")
    uncertainty: str = Field(default="No specific uncertainty noted.", description="Mandatory non-empty uncertainty statement")
    next_questions: list[str] = Field(default_factory=list)
    error_flag: bool = False
    error_message: str | None = None

