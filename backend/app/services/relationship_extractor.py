"""Relationship extraction service.

Derives typed, evidence-backed relationships between security entities directly
from normalized SecurityEvent semantics.

Mapping Rules (from design):
  - LOGGED_INTO      ← user + source_host + action=="login"
                        (Source: User, Target: Host)
  - AUTHENTICATED_TO ← user + destination_host + action=="auth"
                        (Source: User, Target: Server or Host)
  - EXECUTED         ← process + source_host + action=="execute"
                        (Source: Process, Target: Host)
  - CONNECTED_TO     ← source_ip + destination_ip + action=="connect"
                        (Source: IP, Target: IP)
  - ACCESSED         ← (process or user) + file + action=="access"
                        (Source: Process or User, Target: File)

Rule Conditions:
  - Every rule requires BOTH the entity fields AND a matching action value.
  - Action conditions are case-insensitive.
  - Missing or non-matching action value -> NO relationship produced.
  - Unmapped/unsupported field combinations -> NO relationship produced.

Multi-event merging / Deduplication:
  - Multiple events producing the same (source_entity_id, target_entity_id, relationship_type, investigation_id)
    are merged into a single RawRelationship.
  - Contributing event_ids are accumulated in order without duplicates.
  - Timestamp is the earliest timestamp observed among contributing events.

Invariants:
  - Every returned relationship has len(event_ids) >= 1.
  - Relationship type is one of the 5 defined RelationshipType enum members.
  - Source and target entity IDs reference valid extracted entities.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Sequence

from app.schemas.entity import Entity, EntityType, generate_entity_id
from app.schemas.relationship import RawRelationship, RelationshipType
from app.schemas.security_event import SecurityEvent


class RelationshipExtractor:
    """Extract and deduplicate typed relationships from normalized SecurityEvents and extracted Entities."""

    def extract(
        self,
        events: Sequence[SecurityEvent],
        entities: Sequence[Entity],
        investigation_id: str | None = None,
    ) -> list[RawRelationship]:
        """Extract typed relationships derived from events and matched against entities.

        Preconditions:
          - entities covers all entities extracted from events.
          - events are normalized and validated.

        Postconditions:
          - Every relationship references valid source and target entity_ids in entities.
          - Every relationship carries at least one event_id in event_ids.
          - Relationship type is one of LOGGED_INTO, AUTHENTICATED_TO, EXECUTED, CONNECTED_TO, ACCESSED.
        """
        if not events:
            return []

        # Map entities by (entity_type, canonical_key) for fast lookup
        entity_map: dict[tuple[EntityType, str], Entity] = {
            (e.entity_type, e.canonical_key): e for e in entities
        }

        # Accumulator: key -> _RelationshipAccumulator
        acc: dict[tuple[str, str, RelationshipType, str], _RelationshipAccumulator] = {}

        for event in events:
            inv_id = investigation_id or event.investigation_id or getattr(event, "investigation_id", "") or ""
            action_clean = event.action.strip().lower() if event.action else ""

            # 1. LOGGED_INTO: user + source_host + action=="login"
            if action_clean == "login" and event.user and event.source_host:
                user_entity = self._find_entity(entity_map, EntityType.USER, event.user)
                host_entity = self._find_entity(entity_map, EntityType.HOST, event.source_host) or \
                              self._find_entity(entity_map, EntityType.SERVER, event.source_host)

                if user_entity and host_entity:
                    self._upsert(
                        acc=acc,
                        source_entity_id=user_entity.entity_id,
                        target_entity_id=host_entity.entity_id,
                        relationship_type=RelationshipType.LOGGED_INTO,
                        investigation_id=inv_id,
                        timestamp=event.timestamp,
                        event_id=event.event_id,
                        source=event.source_type,
                    )

            # 2. AUTHENTICATED_TO: user + destination_host + action=="auth"
            if action_clean == "auth" and event.user and event.destination_host:
                user_entity = self._find_entity(entity_map, EntityType.USER, event.user)
                server_entity = self._find_entity(entity_map, EntityType.SERVER, event.destination_host) or \
                                self._find_entity(entity_map, EntityType.HOST, event.destination_host)

                if user_entity and server_entity:
                    self._upsert(
                        acc=acc,
                        source_entity_id=user_entity.entity_id,
                        target_entity_id=server_entity.entity_id,
                        relationship_type=RelationshipType.AUTHENTICATED_TO,
                        investigation_id=inv_id,
                        timestamp=event.timestamp,
                        event_id=event.event_id,
                        source=event.source_type,
                    )

            # 3. EXECUTED: process + source_host + action=="execute"
            if action_clean == "execute" and event.process and event.source_host:
                process_key = f"{event.source_host}::{event.process}"
                process_entity = self._find_entity(entity_map, EntityType.PROCESS, process_key)
                host_entity = self._find_entity(entity_map, EntityType.HOST, event.source_host) or \
                              self._find_entity(entity_map, EntityType.SERVER, event.source_host)

                if process_entity and host_entity:
                    self._upsert(
                        acc=acc,
                        source_entity_id=process_entity.entity_id,
                        target_entity_id=host_entity.entity_id,
                        relationship_type=RelationshipType.EXECUTED,
                        investigation_id=inv_id,
                        timestamp=event.timestamp,
                        event_id=event.event_id,
                        source=event.source_type,
                    )

            # 4. CONNECTED_TO: source_ip + destination_ip + action=="connect"
            if action_clean == "connect" and event.source_ip and event.destination_ip:
                src_ip_entity = self._find_entity(entity_map, EntityType.IP, event.source_ip)
                dst_ip_entity = self._find_entity(entity_map, EntityType.IP, event.destination_ip)

                if src_ip_entity and dst_ip_entity:
                    self._upsert(
                        acc=acc,
                        source_entity_id=src_ip_entity.entity_id,
                        target_entity_id=dst_ip_entity.entity_id,
                        relationship_type=RelationshipType.CONNECTED_TO,
                        investigation_id=inv_id,
                        timestamp=event.timestamp,
                        event_id=event.event_id,
                        source=event.source_type,
                    )

            # 5. ACCESSED: (process or user) + file + action=="access"
            if action_clean == "access" and event.file:
                file_key = f"{event.source_host}::{event.file}" if event.source_host else event.file
                file_entity = self._find_entity(entity_map, EntityType.FILE, file_key)

                if file_entity:
                    # Process source
                    if event.process and event.source_host:
                        proc_key = f"{event.source_host}::{event.process}"
                        proc_entity = self._find_entity(entity_map, EntityType.PROCESS, proc_key)
                        if proc_entity:
                            self._upsert(
                                acc=acc,
                                source_entity_id=proc_entity.entity_id,
                                target_entity_id=file_entity.entity_id,
                                relationship_type=RelationshipType.ACCESSED,
                                investigation_id=inv_id,
                                timestamp=event.timestamp,
                                event_id=event.event_id,
                                source=event.source_type,
                            )

                    # User source
                    if event.user:
                        user_entity = self._find_entity(entity_map, EntityType.USER, event.user)
                        if user_entity:
                            self._upsert(
                                acc=acc,
                                source_entity_id=user_entity.entity_id,
                                target_entity_id=file_entity.entity_id,
                                relationship_type=RelationshipType.ACCESSED,
                                investigation_id=inv_id,
                                timestamp=event.timestamp,
                                event_id=event.event_id,
                                source=event.source_type,
                            )

        return [a.to_relationship() for a in acc.values()]

    @staticmethod
    def _find_entity(
        entity_map: dict[tuple[EntityType, str], Entity],
        entity_type: EntityType,
        canonical_key: str,
    ) -> Entity | None:
        found = entity_map.get((entity_type, canonical_key))
        if found is not None:
            return found
        target_id = generate_entity_id(entity_type, canonical_key)
        for entity in entity_map.values():
            if entity.entity_id == target_id:
                return entity
        return None

    @staticmethod
    def _upsert(
        acc: dict[tuple[str, str, RelationshipType, str], _RelationshipAccumulator],
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: RelationshipType,
        investigation_id: str,
        timestamp: datetime,
        event_id: str,
        source: str,
    ) -> None:
        key = (source_entity_id, target_entity_id, relationship_type, investigation_id)
        if key not in acc:
            rel_id_str = hashlib.sha256(
                f"{source_entity_id}:{target_entity_id}:{relationship_type.value}:{investigation_id}".encode("utf-8")
            ).hexdigest()[:16]
            acc[key] = _RelationshipAccumulator(
                relationship_id=rel_id_str,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                relationship_type=relationship_type,
                investigation_id=investigation_id,
                timestamp=timestamp,
                source=source,
            )

        acc[key].add(event_id=event_id, timestamp=timestamp)


class _RelationshipAccumulator:
    __slots__ = (
        "relationship_id",
        "source_entity_id",
        "target_entity_id",
        "relationship_type",
        "investigation_id",
        "timestamp",
        "source",
        "_event_ids",
    )

    def __init__(
        self,
        relationship_id: str,
        source_entity_id: str,
        target_entity_id: str,
        relationship_type: RelationshipType,
        investigation_id: str,
        timestamp: datetime,
        source: str,
    ) -> None:
        self.relationship_id = relationship_id
        self.source_entity_id = source_entity_id
        self.target_entity_id = target_entity_id
        self.relationship_type = relationship_type
        self.investigation_id = investigation_id
        self.timestamp = timestamp
        self.source = source
        self._event_ids: dict[str, None] = {}

    def add(self, event_id: str, timestamp: datetime) -> None:
        self._event_ids[event_id] = None
        if timestamp < self.timestamp:
            self.timestamp = timestamp

    def to_relationship(self) -> RawRelationship:
        return RawRelationship(
            relationship_id=self.relationship_id,
            source_entity_id=self.source_entity_id,
            target_entity_id=self.target_entity_id,
            relationship_type=self.relationship_type,
            investigation_id=self.investigation_id,
            timestamp=self.timestamp,
            event_ids=list(self._event_ids),
            source=self.source,
        )
