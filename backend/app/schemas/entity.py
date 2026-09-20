import hashlib
from enum import Enum
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Supported security entity types."""
    USER = "User"
    HOST = "Host"
    SERVER = "Server"
    IP = "IP"
    PROCESS = "Process"
    FILE = "File"


def generate_entity_id(entity_type: EntityType | str, canonical_key: str) -> str:
    """Generate deterministic entity_id hash from type and canonical key."""
    type_str = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
    key_bytes = f"{type_str}:{canonical_key}".encode("utf-8")
    return hashlib.sha256(key_bytes).hexdigest()[:16]


class Entity(BaseModel):
    """Deduplicated Security Entity."""
    entity_id: str = Field(description="Deterministic hash of (entity_type, canonical_key)")
    entity_type: EntityType = Field(description="Entity classification")
    canonical_key: str = Field(description="Normalized identity key")
    aliases: list[str] = Field(default_factory=list, description="Observed name variants")
    event_ids: list[str] = Field(default_factory=list, description="Evidence event references")
    investigation_id: str = Field(description="Scoping investigation ID")

