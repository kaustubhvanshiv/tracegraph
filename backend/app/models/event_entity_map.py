import uuid
from sqlalchemy import BigInteger, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class EventEntityMapModel(Base):
    """SQLAlchemy model for mapping stored events to extracted entities (for timeline entity cross-linking)."""
    __tablename__ = "event_entity_map"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(Text, nullable=False)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.investigation_id"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("event_id", "investigation_id", "entity_id", name="uq_event_entity_map"),
        Index("idx_event_entity_investigation", "investigation_id"),
        Index("idx_event_entity_event", "event_id", "investigation_id"),
    )
