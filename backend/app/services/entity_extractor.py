"""Entity extraction service.

Identifies and deduplicates User, Host, Server, IP, Process, and File entities
from normalized SecurityEvent objects.

Identity key rules (from design):
  - User    → normalized username (already lowercased / domain-stripped by normalizer)
  - Host    → normalized hostname (lowercase FQDN or short name)
  - Server  → normalized hostname — ONLY when event.raw_data contains a
              'server_role' key, OR event.event_type explicitly contains
              'server' (case-insensitive). Without that signal, use Host.
  - IP      → dotted-decimal IPv4 / compressed IPv6 (already canonicalized)
  - Process → "{source_host}::{process_name}"  (pid is metadata, NOT in key)
  - File    → "{source_host}::{absolute_file_path}"

entity_id is a deterministic SHA-256 hash of "{entity_type}:{canonical_key}",
truncated to 16 hex chars (matches generate_entity_id in schemas/entity.py).

Deduplication: entities with the same entity_id are merged — aliases are
accumulated, event_ids are accumulated, no duplicates within either list.

Invariants:
  - Every returned Entity has at least one event_id (no evidence-less entities).
  - All entity_id values in the output are unique.
  - The result is deterministic for identical input.
"""

from __future__ import annotations

from app.schemas.entity import Entity, EntityType, generate_entity_id
from app.schemas.security_event import SecurityEvent

# ---------------------------------------------------------------------------
# Internal accumulator used during deduplication
# ---------------------------------------------------------------------------

_SERVER_ROLE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "server_access",
        "server_authentication",
        "server_connection",
        "server_event",
    }
)


class EntityExtractor:
    """Extract and deduplicate security entities from normalized SecurityEvents.

    Usage::

        extractor = EntityExtractor()
        entities = extractor.extract(events, investigation_id="inv-001")
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        events: list[SecurityEvent],
        investigation_id: str,
    ) -> list[Entity]:
        """Extract entities from *events*, deduplicating by (type, canonical_key).

        Preconditions:
          - events is a non-empty list of validated SecurityEvent objects
          - investigation_id is a non-empty string

        Postconditions:
          - ∀ e ∈ result: len(e.event_ids) >= 1
          - ∀ e1, e2 ∈ result: e1 ≠ e2 → e1.entity_id ≠ e2.entity_id
          - ∀ event ∈ events with extractable fields: ∃ entity s.t. event_id ∈ entity.event_ids
          - len(result) is deterministic for the same input
        """
        # accumulator: entity_id → _EntityAccumulator
        acc: dict[str, _EntityAccumulator] = {}

        for event in events:
            self._extract_from_event(event, investigation_id, acc)

        return [a.to_entity() for a in acc.values()]

    # ------------------------------------------------------------------
    # Private: per-event extraction
    # ------------------------------------------------------------------

    def _extract_from_event(
        self,
        event: SecurityEvent,
        investigation_id: str,
        acc: dict[str, "_EntityAccumulator"],
    ) -> None:
        """Dispatch entity extraction for every recognizable field in *event*."""
        # --- User ---
        if event.user:
            self._upsert(
                acc=acc,
                entity_type=EntityType.USER,
                canonical_key=event.user,
                alias=event.user,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        # --- Host / Server ---
        # source_host
        if event.source_host:
            entity_type = self._classify_host_or_server(event)
            self._upsert(
                acc=acc,
                entity_type=entity_type,
                canonical_key=event.source_host,
                alias=event.source_host,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        # destination_host — always Host (destination is typically a host being
        # reached, not necessarily a configured server; server_role applies
        # to the source/reporting host only).
        if event.destination_host:
            self._upsert(
                acc=acc,
                entity_type=EntityType.HOST,
                canonical_key=event.destination_host,
                alias=event.destination_host,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        # --- IP ---
        if event.source_ip:
            self._upsert(
                acc=acc,
                entity_type=EntityType.IP,
                canonical_key=event.source_ip,
                alias=event.source_ip,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        if event.destination_ip:
            self._upsert(
                acc=acc,
                entity_type=EntityType.IP,
                canonical_key=event.destination_ip,
                alias=event.destination_ip,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        # --- Process ---
        # Requires both source_host AND process name to form a stable canonical key.
        if event.process and event.source_host:
            canonical_key = f"{event.source_host}::{event.process}"
            self._upsert(
                acc=acc,
                entity_type=EntityType.PROCESS,
                canonical_key=canonical_key,
                alias=event.process,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

        # --- File ---
        # Requires both source_host AND absolute file path.
        if event.file and event.source_host:
            canonical_key = f"{event.source_host}::{event.file}"
            self._upsert(
                acc=acc,
                entity_type=EntityType.FILE,
                canonical_key=canonical_key,
                alias=event.file,
                event_id=event.event_id,
                investigation_id=investigation_id,
            )

    # ------------------------------------------------------------------
    # Private: Server vs Host classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_host_or_server(event: SecurityEvent) -> EntityType:
        """Return SERVER if the event signals a server role; otherwise HOST.

        Server classification applies only when:
          1. event.raw_data contains a non-empty 'server_role' key, OR
          2. event.event_type (lowercased) contains the word 'server'

        Design note: pid is NOT part of the Process canonical_key.
        """
        # Check raw_data for an explicit server_role field
        if event.raw_data:
            server_role = event.raw_data.get("server_role")
            if server_role and str(server_role).strip():
                return EntityType.SERVER

        # Check event_type for server hint (e.g. "server_access", "server_auth")
        if event.event_type and "server" in event.event_type.lower():
            return EntityType.SERVER

        return EntityType.HOST

    # ------------------------------------------------------------------
    # Private: accumulator upsert
    # ------------------------------------------------------------------

    @staticmethod
    def _upsert(
        acc: dict[str, "_EntityAccumulator"],
        entity_type: EntityType,
        canonical_key: str,
        alias: str,
        event_id: str,
        investigation_id: str,
    ) -> None:
        """Insert or merge an entity into *acc*."""
        entity_id = generate_entity_id(entity_type, canonical_key)

        if entity_id not in acc:
            acc[entity_id] = _EntityAccumulator(
                entity_id=entity_id,
                entity_type=entity_type,
                canonical_key=canonical_key,
                investigation_id=investigation_id,
            )

        acc[entity_id].add(alias=alias, event_id=event_id)


# ---------------------------------------------------------------------------
# Internal accumulator (not exported)
# ---------------------------------------------------------------------------


class _EntityAccumulator:
    """Mutable accumulator for a single deduplicated entity during extraction."""

    __slots__ = (
        "entity_id",
        "entity_type",
        "canonical_key",
        "investigation_id",
        "_aliases",
        "_event_ids",
    )

    def __init__(
        self,
        entity_id: str,
        entity_type: EntityType,
        canonical_key: str,
        investigation_id: str,
    ) -> None:
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.canonical_key = canonical_key
        self.investigation_id = investigation_id
        # Use ordered sets (insertion-order dict keys) to preserve determinism
        self._aliases: dict[str, None] = {}
        self._event_ids: dict[str, None] = {}

    def add(self, alias: str, event_id: str) -> None:
        """Record *alias* and *event_id* for this entity."""
        self._aliases[alias] = None
        self._event_ids[event_id] = None

    def to_entity(self) -> Entity:
        """Materialise as an immutable Entity schema object."""
        return Entity(
            entity_id=self.entity_id,
            entity_type=self.entity_type,
            canonical_key=self.canonical_key,
            aliases=list(self._aliases),
            event_ids=list(self._event_ids),
            investigation_id=self.investigation_id,
        )
