"""Neo4j graph repository.

Idempotent upsert semantics using MERGE patterns (parameterized Cypher only —
no string interpolation of user-controlled values).

Node labels and relationship types come from trusted enums (EntityType,
RelationshipType), not from user input. Because Neo4j does not support
parameterized labels/relationship-types, we whitelist against the enum values
and use safe string formatting on those controlled strings only.

Methods:
  upsert_entity        — MERGE node on (canonical_key, investigation_id)
  upsert_relationship  — MERGE relationship on (source_id, target_id, type, inv_id)
  get_graph            — filtered graph retrieval for an investigation
  pivot                — multi-hop traversal from a given entity_id
  get_entity           — entity detail with relationships + accumulated event_ids

Error behaviour:
  On any ServiceUnavailable, AuthError, or Neo4jError (connection-level), raises
  GraphUnavailableError (HTTP 503, code GRAPH_UNAVAILABLE).  Never silently
  succeeds when Neo4j is unreachable.

Requirements: 8.1–8.10, 15.7
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncDriver  # type: ignore[import-untyped]
from neo4j.exceptions import (  # type: ignore[import-untyped]
    AuthError,
    Neo4jError,
    ServiceUnavailable,
)

from app.core.errors import GraphUnavailableError
from app.schemas.entity import Entity, EntityType
from app.schemas.graph import EntityDetail, GraphFilter, GraphResult
from app.schemas.relationship import CorrelatedRelationship, RelationshipType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelists (derived from trusted enums — never from user input)
# ---------------------------------------------------------------------------

_VALID_LABELS: frozenset[str] = frozenset(e.value for e in EntityType)
_VALID_REL_TYPES: frozenset[str] = frozenset(e.value for e in RelationshipType)


def _assert_safe_label(label: str) -> str:
    """Validate that *label* is a known EntityType value before embedding in Cypher."""
    if label not in _VALID_LABELS:
        raise ValueError(f"Unknown entity label: {label!r}")
    return label


def _assert_safe_rel_type(rel_type: str) -> str:
    """Validate that *rel_type* is a known RelationshipType value before embedding in Cypher."""
    if rel_type not in _VALID_REL_TYPES:
        raise ValueError(f"Unknown relationship type: {rel_type!r}")
    return rel_type


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _dt_to_iso(dt: datetime) -> str:
    """Serialise a datetime to a UTC ISO-8601 string for Neo4j storage."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _iso_to_dt(value: Any) -> datetime:
    """Parse an ISO-8601 string (or datetime) back to a UTC-aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    # Neo4j may return neo4j.time.DateTime — convert via str → datetime.fromisoformat
    dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Result mapping helpers
# ---------------------------------------------------------------------------

def _record_to_entity(node: Any) -> Entity:
    """Convert a Neo4j node to an Entity schema object."""
    props = dict(node)
    return Entity(
        entity_id=props["entity_id"],
        entity_type=EntityType(props["entity_type"]),
        canonical_key=props["canonical_key"],
        aliases=list(props.get("aliases") or []),
        event_ids=list(props.get("event_ids") or []),
        investigation_id=props["investigation_id"],
    )


def _record_to_relationship(rel: Any) -> CorrelatedRelationship:
    """Convert a Neo4j relationship to a CorrelatedRelationship schema object."""
    props = dict(rel)
    raw_scores = props.get("signal_scores", "{}")
    if isinstance(raw_scores, str):
        signal_scores: dict[str, float] = json.loads(raw_scores)
    elif isinstance(raw_scores, dict):
        signal_scores = {k: float(v) for k, v in raw_scores.items()}
    else:
        signal_scores = {}

    return CorrelatedRelationship(
        relationship_id=props["relationship_id"],
        source_entity_id=props["source_entity_id"],
        target_entity_id=props["target_entity_id"],
        relationship_type=RelationshipType(props["relationship_type"]),
        investigation_id=props["investigation_id"],
        timestamp=_iso_to_dt(props["timestamp"]),
        event_ids=list(props.get("event_ids") or []),
        source=props["source"],
        signal_names=list(props.get("signal_names") or []),
        signal_scores=signal_scores,
        combined_score=float(props.get("combined_score", 0.0)),
        explanation=props.get("explanation", ""),
    )


# ---------------------------------------------------------------------------
# GraphRepository
# ---------------------------------------------------------------------------

class GraphRepository:
    """Neo4j graph persistence and query operations.

    The repository takes an ``AsyncDriver`` (injected at construction time)
    rather than importing the global ``neo4j_driver`` directly, which keeps it
    fully testable in isolation.
    """

    def __init__(self, driver: AsyncDriver) -> None:
        self._driver = driver

    # ------------------------------------------------------------------
    # upsert_entity
    # ------------------------------------------------------------------

    async def upsert_entity(self, entity: Entity) -> None:
        """Idempotent upsert of a single entity node.

        MERGE on (canonical_key, investigation_id) to guarantee per-investigation
        scoping (Requirement 19.4).

        ON CREATE: set all properties.
        ON MATCH: append only new aliases and event_ids (no duplicates, never
                  destructively overwrite existing data).

        Because Neo4j does not support parameterized node labels, the label is
        derived from the EntityType enum (a controlled value, not user input)
        and validated against the whitelist before embedding in Cypher.
        """
        label = _assert_safe_label(entity.entity_type.value)

        # Build the query with the safe label embedded.
        # All other values go through $params — never interpolated.
        query = f"""
            MERGE (n:{label} {{canonical_key: $canonical_key, investigation_id: $investigation_id}})
            ON CREATE SET
                n.entity_id        = $entity_id,
                n.entity_type      = $entity_type,
                n.canonical_key    = $canonical_key,
                n.investigation_id = $investigation_id,
                n.aliases          = $aliases,
                n.event_ids        = $event_ids
            ON MATCH SET
                n.aliases    = n.aliases    + [x IN $aliases    WHERE NOT x IN n.aliases],
                n.event_ids  = n.event_ids  + [x IN $event_ids  WHERE NOT x IN n.event_ids]
        """
        params: dict[str, Any] = {
            "entity_id":        entity.entity_id,
            "entity_type":      entity.entity_type.value,
            "canonical_key":    entity.canonical_key,
            "investigation_id": entity.investigation_id,
            "aliases":          entity.aliases,
            "event_ids":        entity.event_ids,
        }

        try:
            async with self._driver.session() as session:
                await session.run(query, params)
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j upsert_entity failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during entity upsert."
            ) from exc

    # ------------------------------------------------------------------
    # upsert_relationship
    # ------------------------------------------------------------------

    async def upsert_relationship(self, rel: CorrelatedRelationship) -> None:
        """Idempotent upsert of a correlated relationship.

        MERGE on (source_entity_id, target_entity_id, relationship_type,
                  investigation_id).

        ON CREATE: set all required properties.
        ON MATCH:  append new event_ids and signal_names without duplicates.
                   NEVER remove existing entries (Req 8.4, 8.5).

        ``signal_scores`` (dict[str, float]) is serialised to a JSON string
        because Neo4j relationships do not natively support nested maps.

        The relationship type label is derived from RelationshipType enum and
        validated against the whitelist before being embedded in Cypher.
        """
        rel_type = _assert_safe_rel_type(rel.relationship_type.value)
        timestamp_str = _dt_to_iso(rel.timestamp)
        signal_scores_json = json.dumps(rel.signal_scores)

        # MERGE requires locating source and target nodes by entity_id first.
        # We match any node (regardless of label) on entity_id + investigation_id
        # to keep the query generic across all entity types.
        query = f"""
            MATCH (src {{entity_id: $source_entity_id, investigation_id: $investigation_id}})
            MATCH (tgt {{entity_id: $target_entity_id, investigation_id: $investigation_id}})
            MERGE (src)-[r:{rel_type} {{
                source_entity_id: $source_entity_id,
                target_entity_id: $target_entity_id,
                investigation_id: $investigation_id
            }}]->(tgt)
            ON CREATE SET
                r.relationship_id   = $relationship_id,
                r.relationship_type = $relationship_type,
                r.source_entity_id  = $source_entity_id,
                r.target_entity_id  = $target_entity_id,
                r.investigation_id  = $investigation_id,
                r.timestamp         = $timestamp,
                r.event_ids         = $event_ids,
                r.source            = $source,
                r.signal_names      = $signal_names,
                r.signal_scores     = $signal_scores,
                r.combined_score    = $combined_score,
                r.explanation       = $explanation
            ON MATCH SET
                r.event_ids    = r.event_ids    + [x IN $event_ids    WHERE NOT x IN r.event_ids],
                r.signal_names = r.signal_names + [x IN $signal_names WHERE NOT x IN r.signal_names]
        """
        params: dict[str, Any] = {
            "relationship_id":   rel.relationship_id,
            "relationship_type": rel.relationship_type.value,
            "source_entity_id":  rel.source_entity_id,
            "target_entity_id":  rel.target_entity_id,
            "investigation_id":  rel.investigation_id,
            "timestamp":         timestamp_str,
            "event_ids":         rel.event_ids,
            "source":            rel.source,
            "signal_names":      rel.signal_names,
            "signal_scores":     signal_scores_json,
            "combined_score":    rel.combined_score,
            "explanation":       rel.explanation,
        }

        try:
            async with self._driver.session() as session:
                await session.run(query, params)
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j upsert_relationship failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during relationship upsert."
            ) from exc

    # ------------------------------------------------------------------
    # get_graph
    # ------------------------------------------------------------------

    async def get_graph(
        self,
        investigation_id: str,
        filters: GraphFilter,
    ) -> GraphResult:
        """Return all nodes and relationships for an investigation.

        Applies optional filters:
          - entity_type:        restrict nodes to a specific label
          - relationship_type:  restrict edges to a specific relationship type
          - start_time/end_time: restrict edges by timestamp range

        Returns an empty GraphResult (not an error) when the investigation has
        no data yet.  Raises GraphUnavailableError on connection failure.
        """
        # Build the node-match clause.  Label filtering requires embedding a
        # trusted enum value in the Cypher — validated by whitelist.
        if filters.entity_type is not None:
            node_label = _assert_safe_label(filters.entity_type.value)
            node_match = f"MATCH (n:{node_label} {{investigation_id: $investigation_id}})"
        else:
            node_match = "MATCH (n {investigation_id: $investigation_id})"

        # Build the relationship-match clause with optional filters.
        # All date comparisons use parameterized values.
        if filters.relationship_type is not None:
            rel_label = _assert_safe_rel_type(filters.relationship_type.value)
            rel_match = (
                f"MATCH (a {{investigation_id: $investigation_id}})"
                f"-[r:{rel_label}]->"
                f"(b {{investigation_id: $investigation_id}})"
            )
        else:
            rel_match = (
                "MATCH (a {investigation_id: $investigation_id})"
                "-[r]->"
                "(b {investigation_id: $investigation_id})"
            )

        # Time-range filter on relationship timestamp.
        time_conditions: list[str] = []
        if filters.start_time is not None:
            time_conditions.append("r.timestamp >= $start_time")
        if filters.end_time is not None:
            time_conditions.append("r.timestamp <= $end_time")

        where_clause = ""
        if time_conditions:
            where_clause = "WHERE " + " AND ".join(time_conditions)

        node_query = f"""
            {node_match}
            RETURN n
        """
        rel_query = f"""
            {rel_match}
            {where_clause}
            RETURN r
        """

        params: dict[str, Any] = {"investigation_id": investigation_id}
        if filters.start_time is not None:
            params["start_time"] = _dt_to_iso(filters.start_time)
        if filters.end_time is not None:
            params["end_time"] = _dt_to_iso(filters.end_time)

        try:
            async with self._driver.session() as session:
                node_result = await session.run(node_query, params)
                node_records = await node_result.data()

                rel_result = await session.run(rel_query, params)
                rel_records = await rel_result.data()
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j get_graph failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during graph retrieval."
            ) from exc

        nodes: list[Entity] = []
        for record in node_records:
            try:
                nodes.append(_record_to_entity(record["n"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed node record: %s", exc)

        edges: list[CorrelatedRelationship] = []
        for record in rel_records:
            try:
                edges.append(_record_to_relationship(record["r"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed relationship record: %s", exc)

        return GraphResult(
            investigation_id=investigation_id,
            nodes=nodes,
            edges=edges,
        )

    # ------------------------------------------------------------------
    # pivot
    # ------------------------------------------------------------------

    async def pivot(
        self,
        entity_id: str,
        investigation_id: str,
        hops: int = 2,
    ) -> GraphResult:
        """Multi-hop traversal from a given entity_id.

        Returns all nodes and relationships reachable within *hops* steps
        (undirected) from the starting entity, scoped to *investigation_id*.

        *hops* is an integer from the method signature (not user-controlled
        input that could be arbitrarily large), so embedding it as a literal
        in the Cypher path pattern is safe.  We clamp it to [1, 10] as a
        defensive guard.
        """
        hops = max(1, min(hops, 10))  # defensive clamp

        # Variable-length path pattern.  hops is an integer literal, not a
        # user string — safe to embed directly.
        query = f"""
            MATCH path = (start {{entity_id: $entity_id, investigation_id: $inv_id}})
                         -[*1..{hops}]-
                         (connected {{investigation_id: $inv_id}})
            UNWIND nodes(path)         AS n
            UNWIND relationships(path) AS r
            RETURN DISTINCT n, r
        """
        params: dict[str, Any] = {
            "entity_id": entity_id,
            "inv_id":    investigation_id,
        }

        try:
            async with self._driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j pivot failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during pivot traversal."
            ) from exc

        seen_nodes: dict[str, Entity] = {}
        seen_edges: dict[str, CorrelatedRelationship] = {}

        for record in records:
            # Node
            try:
                node_props = dict(record["n"])
                eid = node_props.get("entity_id", "")
                if eid and eid not in seen_nodes:
                    seen_nodes[eid] = _record_to_entity(record["n"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed node in pivot: %s", exc)

            # Relationship
            try:
                rel_props = dict(record["r"])
                rid = rel_props.get("relationship_id", "")
                if rid and rid not in seen_edges:
                    seen_edges[rid] = _record_to_relationship(record["r"])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed relationship in pivot: %s", exc)

        # Also include the starting node itself (path unwind skips it when
        # it's isolated — query returns no rows if no paths exist).
        if not seen_nodes:
            # Attempt to fetch just the start node so it appears in the result.
            start_query = """
                MATCH (n {entity_id: $entity_id, investigation_id: $inv_id})
                RETURN n
            """
            try:
                async with self._driver.session() as session:
                    result = await session.run(start_query, params)
                    start_records = await result.data()
                for rec in start_records:
                    node = _record_to_entity(rec["n"])
                    seen_nodes[node.entity_id] = node
            except (ServiceUnavailable, AuthError, Neo4jError) as exc:
                logger.error("Neo4j pivot start-node fetch failed: %s", exc)
                raise GraphUnavailableError(
                    "Neo4j is unreachable or returned an error during pivot start-node fetch."
                ) from exc

        return GraphResult(
            investigation_id=investigation_id,
            nodes=list(seen_nodes.values()),
            edges=list(seen_edges.values()),
        )

    # ------------------------------------------------------------------
    # get_entity
    # ------------------------------------------------------------------

    async def get_entity(
        self,
        entity_id: str,
        investigation_id: str,
    ) -> EntityDetail:
        """Return EntityDetail for a single entity scoped to an investigation.

        Includes:
          - The entity itself
          - All relationships where the entity is source or target
          - Accumulated event_ids from the entity + all its relationships

        Raises GraphUnavailableError on connection failure.
        Raises KeyError (surfaced as 404 by the caller) if no node is found.
        """
        node_query = """
            MATCH (n {entity_id: $entity_id, investigation_id: $investigation_id})
            RETURN n
        """
        rel_query = """
            MATCH (n {entity_id: $entity_id, investigation_id: $investigation_id})
            MATCH (n)-[r]-(other {investigation_id: $investigation_id})
            RETURN DISTINCT r
        """
        params: dict[str, Any] = {
            "entity_id":        entity_id,
            "investigation_id": investigation_id,
        }

        try:
            async with self._driver.session() as session:
                node_result = await session.run(node_query, params)
                node_records = await node_result.data()

                rel_result = await session.run(rel_query, params)
                rel_records = await rel_result.data()
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j get_entity failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during entity retrieval."
            ) from exc

        if not node_records:
            raise KeyError(
                f"Entity {entity_id!r} not found in investigation {investigation_id!r}"
            )

        entity = _record_to_entity(node_records[0]["n"])

        relationships: list[CorrelatedRelationship] = []
        for record in rel_records:
            try:
                relationships.append(_record_to_relationship(record["r"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed relationship in get_entity: %s", exc)

        # Accumulate all event_ids: entity's own + all relationship evidence
        all_event_ids: list[str] = list(entity.event_ids)
        seen_eids: set[str] = set(all_event_ids)
        for rel in relationships:
            for eid in rel.event_ids:
                if eid not in seen_eids:
                    all_event_ids.append(eid)
                    seen_eids.add(eid)

        return EntityDetail(
            entity=entity,
            relationships=relationships,
            event_ids=all_event_ids,
        )

    # ------------------------------------------------------------------
    # get_entities_for_event
    # ------------------------------------------------------------------

    async def get_entities_for_event(
        self,
        event_id: str,
        investigation_id: str,
    ) -> list[Entity]:
        """Return all entity nodes associated with *event_id* in an investigation."""
        query = """
            MATCH (n {investigation_id: $investigation_id})
            WHERE $event_id IN n.event_ids
            RETURN DISTINCT n
        """
        params: dict[str, Any] = {
            "event_id": event_id,
            "investigation_id": investigation_id,
        }

        try:
            async with self._driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j get_entities_for_event failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during event entity lookup."
            ) from exc

        entities: list[Entity] = []
        for record in records:
            try:
                entities.append(_record_to_entity(record["n"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed node in get_entities_for_event: %s", exc)

        return entities

    # ------------------------------------------------------------------
    # get_relationships_for_event
    # ------------------------------------------------------------------

    async def get_relationships_for_event(
        self,
        event_id: str,
        investigation_id: str,
    ) -> list[CorrelatedRelationship]:
        """Return all correlated relationships referencing *event_id* in an investigation."""
        query = """
            MATCH (a {investigation_id: $investigation_id})-[r]->(b {investigation_id: $investigation_id})
            WHERE $event_id IN r.event_ids
            RETURN DISTINCT r
        """
        params: dict[str, Any] = {
            "event_id": event_id,
            "investigation_id": investigation_id,
        }

        try:
            async with self._driver.session() as session:
                result = await session.run(query, params)
                records = await result.data()
        except (ServiceUnavailable, AuthError, Neo4jError) as exc:
            logger.error("Neo4j get_relationships_for_event failed: %s", exc)
            raise GraphUnavailableError(
                "Neo4j is unreachable or returned an error during event relationship lookup."
            ) from exc

        relationships: list[CorrelatedRelationship] = []
        for record in records:
            try:
                relationships.append(_record_to_relationship(record["r"]))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping malformed relationship in get_relationships_for_event: %s", exc)

        return relationships

