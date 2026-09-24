from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

# SecurityEvent is imported here for CandidatePair; the TYPE_CHECKING guard is
# intentionally NOT used because Pydantic v2 needs the real class at model
# construction time (not just for type annotations).
from app.schemas.security_event import SecurityEvent  # noqa: E402


class RelationshipType(str, Enum):
    """Supported entity relationship types."""
    LOGGED_INTO = "LOGGED_INTO"
    AUTHENTICATED_TO = "AUTHENTICATED_TO"
    EXECUTED = "EXECUTED"
    CONNECTED_TO = "CONNECTED_TO"
    ACCESSED = "ACCESSED"


class RawRelationship(BaseModel):
    """Raw relationship extracted directly from event semantics before temporal correlation."""
    relationship_id: str = Field(description="Unique relationship identifier")
    source_entity_id: str = Field(description="Source entity ID")
    target_entity_id: str = Field(description="Target entity ID")
    relationship_type: RelationshipType = Field(description="Typed relationship kind")
    investigation_id: str = Field(description="Scoping investigation ID")
    timestamp: datetime = Field(description="Trigger event timestamp")
    event_ids: list[str] = Field(default_factory=list, description="Evidence event references")
    source: str = Field(description="Parser source_type")


class CorrelatedRelationship(BaseModel):
    """Enriched relationship produced by temporal correlation with fired signals and explanations."""
    relationship_id: str = Field(description="Unique relationship identifier")
    source_entity_id: str = Field(description="Source entity ID")
    target_entity_id: str = Field(description="Target entity ID")
    relationship_type: RelationshipType = Field(description="Typed relationship kind")
    investigation_id: str = Field(description="Scoping investigation ID")
    timestamp: datetime = Field(description="Trigger event timestamp")
    event_ids: list[str] = Field(default_factory=list, description="Evidence event references")
    source: str = Field(description="Parser source_type")
    signal_names: list[str] = Field(default_factory=list, description="Correlation signal names that fired")
    signal_scores: dict[str, float] = Field(default_factory=dict, description="Per-signal score breakdown")
    combined_score: float = Field(description="Weighted sum normalized to [0.0, 1.0]")
    explanation: str = Field(description="Human-readable explanation of correlation")



class CandidatePair(BaseModel):
    """
    A pair of SecurityEvents that are candidates for temporal correlation.

    Invariants:
      - event_a.timestamp <= event_b.timestamp (a is always the earlier event)
      - event_a.event_id != event_b.event_id (never self-pairs)
      - Both events belong to the same investigation_id
    """
    event_a: SecurityEvent = Field(description="Earlier event in the candidate pair")
    event_b: SecurityEvent = Field(description="Later event in the candidate pair")
    investigation_id: str = Field(description="Shared investigation scope for both events")
    delta_seconds: float = Field(
        description="Time delta between events in seconds (b.timestamp - a.timestamp)"
    )


