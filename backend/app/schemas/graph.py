from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.entity import Entity, EntityType
from app.schemas.relationship import CorrelatedRelationship, RelationshipType


class GraphFilter(BaseModel):
    """Filter criteria for graph queries."""
    entity_type: EntityType | None = None
    relationship_type: RelationshipType | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class GraphResult(BaseModel):
    """Graph query response with nodes and edges."""
    investigation_id: str
    nodes: list[Entity] = Field(default_factory=list)
    edges: list[CorrelatedRelationship] = Field(default_factory=list)


class EntityDetail(BaseModel):
    """Detailed view for a single entity including connected evidence."""
    entity: Entity
    relationships: list[CorrelatedRelationship] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)

