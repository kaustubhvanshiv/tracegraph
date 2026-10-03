"""Graph query API routes.

Endpoints (implemented in task 17.1):
  GET /api/investigations/{id}/graph
  GET /api/investigations/{id}/graph/pivot
  GET /api/investigations/{id}/entities/{eid}

Security:
  - JWT required (get_current_user dependency).
  - Investigation ownership enforced (same pattern as events.py).

Requirements: 8.8, 8.9, 8.10, 16.5
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from neo4j import AsyncDriver  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.core.errors import ForbiddenError, GraphUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.graph import EntityDetail, GraphFilter, GraphResult, EntityType, RelationshipType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["graph"])


# ---------------------------------------------------------------------------
# Helper — ownership enforcement
# ---------------------------------------------------------------------------


async def _check_investigation_ownership(
    investigation_id: str,
    current_user: CurrentUser,
    db: AsyncSession,
) -> None:
    """Raise ForbiddenError if the caller is not the investigation owner.

    Treats 'not found' and 'wrong owner' identically to avoid leaking
    existence information to non-owners.
    """
    inv_repo = InvestigationRepository(db)
    row = await inv_repo.get_by_id(investigation_id)
    if row is None or str(row.owner_id) != current_user.user_id:
        raise ForbiddenError(
            "You do not have permission to access this investigation."
        )


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/graph — full graph
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/graph",
    response_model=SuccessResponse[GraphResult],
    status_code=200,
    summary="Get full investigation graph with optional filters",
)
async def get_graph(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    entity_type: Annotated[
        EntityType | None,
        Query(description="Filter nodes by entity type"),
    ] = None,
    relationship_type: Annotated[
        RelationshipType | None,
        Query(description="Filter edges by relationship type"),
    ] = None,
    start_time: Annotated[
        str | None,
        Query(description="Filter edges on or after this UTC timestamp (ISO-8601)"),
    ] = None,
    end_time: Annotated[
        str | None,
        Query(description="Filter edges on or before this UTC timestamp (ISO-8601)"),
    ] = None,
) -> SuccessResponse[GraphResult]:
    """Retrieve the full investigation graph with optional filtering.

    Returns all nodes and relationships for the investigation.  Supports
    optional filtering by entity type, relationship type, and time range.

    Raises GRAPH_UNAVAILABLE (503) when Neo4j is unreachable; does not return
    empty results silently.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    from datetime import datetime

    filters = GraphFilter(
        entity_type=entity_type,
        relationship_type=relationship_type,
        start_time=datetime.fromisoformat(start_time) if start_time else None,
        end_time=datetime.fromisoformat(end_time) if end_time else None,
    )

    logger.info(
        "Graph request",
        extra={
            "investigation_id": investigation_id,
            "filters": {
                "entity_type": entity_type.value if entity_type else None,
                "relationship_type": relationship_type.value if relationship_type else None,
                "start_time": start_time,
                "end_time": end_time,
            },
        },
    )

    repo = GraphRepository(neo4j_driver)
    try:
        result = await repo.get_graph(investigation_id, filters)
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during graph retrieval."
        ) from exc

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/graph/pivot — multi-hop pivot
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/graph/pivot",
    response_model=SuccessResponse[GraphResult],
    status_code=200,
    summary="Multi-hop pivot from an entity",
)
async def pivot_graph(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    entity_id: Annotated[str, Query(alias="entity_id", description="Starting entity ID")],
    hops: Annotated[
        int,
        Query(ge=1, le=10, description="Number of hops (default 2, max 10)"),
    ] = 2,
) -> SuccessResponse[GraphResult]:
    """Perform a multi-hop pivot traversal from a given entity.

    Returns all nodes and relationships reachable within *hops* steps
    (undirected) from the starting entity, scoped to the investigation.

    Raises GRAPH_UNAVAILABLE (503) when Neo4j is unreachable.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Pivot request",
        extra={
            "investigation_id": investigation_id,
            "entity_id": entity_id,
            "hops": hops,
        },
    )

    repo = GraphRepository(neo4j_driver)
    try:
        result = await repo.pivot(entity_id, investigation_id, hops)
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Pivot query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during pivot traversal."
        ) from exc

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/entities/{eid} — entity detail
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/entities/{entity_id}",
    response_model=SuccessResponse[EntityDetail],
    status_code=200,
    summary="Get entity detail with relationships and evidence",
)
async def get_entity(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    entity_id: Annotated[str, Path(description="Target entity ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[EntityDetail]:
    """Retrieve detailed information for a single entity.

    Includes the entity itself, all connected relationships, and accumulated
    event IDs from both the entity and its relationships.

    Raises GRAPH_UNAVAILABLE (503) when Neo4j is unreachable.
    Returns 404 if the entity does not exist in the investigation.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Entity detail request",
        extra={
            "investigation_id": investigation_id,
            "entity_id": entity_id,
        },
    )

    repo = GraphRepository(neo4j_driver)
    try:
        result = await repo.get_entity(entity_id, investigation_id)
    except KeyError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Entity detail query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during entity retrieval."
        ) from exc

    return SuccessResponse(data=result)