"""Graph query API routes.

Endpoints:
  GET /api/investigations/{investigation_id}/graph
  GET /api/investigations/{investigation_id}/graph/pivot
  GET /api/investigations/{investigation_id}/entities/{entity_id}

Security:
  - JWT required on all endpoints (get_current_user dependency).
  - Investigation ownership enforced.

Requirements: 8.8, 8.9, 8.10, 16.5
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from neo4j import AsyncDriver  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.core.errors import EntityNotFoundError, ForbiddenError, GraphUnavailableError
from app.repositories.graph_repository import GraphRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.entity import EntityType
from app.schemas.graph import EntityDetail, GraphFilter, GraphResult
from app.schemas.relationship import RelationshipType

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
# GET /api/investigations/{investigation_id}/graph
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/graph",
    response_model=SuccessResponse[GraphResult],
    status_code=200,
    summary="Retrieve full investigation graph with optional filters",
)
async def get_graph(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    entity_type: Annotated[
        EntityType | None,
        Query(description="Filter nodes to a specific entity type"),
    ] = None,
    relationship_type: Annotated[
        RelationshipType | None,
        Query(description="Filter relationships to a specific type"),
    ] = None,
    start_time: Annotated[
        datetime | None,
        Query(description="Filter relationships on or after this UTC timestamp"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter relationships on or before this UTC timestamp"),
    ] = None,
) -> SuccessResponse[GraphResult]:
    """Retrieve all entity nodes and correlated relationships for an investigation.

    Applies optional filters by entity_type, relationship_type, start_time, and end_time.
    Returns HTTP 503 (GRAPH_UNAVAILABLE) if Neo4j is unreachable.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    filters = GraphFilter(
        entity_type=entity_type,
        relationship_type=relationship_type,
        start_time=start_time,
        end_time=end_time,
    )

    logger.info(
        "Graph retrieval request",
        extra={
            "investigation_id": investigation_id,
            "filters": {
                "entity_type": entity_type.value if entity_type else None,
                "relationship_type": relationship_type.value if relationship_type else None,
                "start_time": str(start_time) if start_time else None,
                "end_time": str(end_time) if end_time else None,
            },
        },
    )

    graph_repo = GraphRepository(neo4j_driver)
    try:
        result = await graph_repo.get_graph(
            investigation_id=investigation_id,
            filters=filters,
        )
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Graph query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during graph retrieval."
        ) from exc

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/graph/pivot
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/graph/pivot",
    response_model=SuccessResponse[GraphResult],
    status_code=200,
    summary="Multi-hop graph pivot from a given entity_id",
)
async def pivot_graph(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    entity_id: Annotated[str, Query(alias="entity_id", description="Starting entity ID for pivot")],
    hops: Annotated[
        int,
        Query(ge=1, le=10, description="Max hop depth for traversal (default: 2)"),
    ] = 2,
) -> SuccessResponse[GraphResult]:
    """Perform a multi-hop traversal starting from entity_id up to max hops.

    Returns all reachable nodes and relationships within hop depth scoped to
    the investigation. Returns HTTP 503 (GRAPH_UNAVAILABLE) if Neo4j is unreachable.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Graph pivot request",
        extra={
            "investigation_id": investigation_id,
            "entity_id": entity_id,
            "hops": hops,
        },
    )

    graph_repo = GraphRepository(neo4j_driver)
    try:
        result = await graph_repo.pivot(
            entity_id=entity_id,
            investigation_id=investigation_id,
            hops=hops,
        )
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Pivot query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during pivot traversal."
        ) from exc

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/entities/{entity_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/entities/{entity_id}",
    response_model=SuccessResponse[EntityDetail],
    status_code=200,
    summary="Retrieve detail for a single entity with evidence references",
)
async def get_entity_detail(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    entity_id: Annotated[str, Path(description="Target entity ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[EntityDetail]:
    """Retrieve detailed entity record including all relationships and accumulated event_ids.

    Returns HTTP 404 (ENTITY_NOT_FOUND) if the entity does not exist in the investigation.
    Returns HTTP 503 (GRAPH_UNAVAILABLE) if Neo4j is unreachable.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Entity detail request",
        extra={
            "investigation_id": investigation_id,
            "entity_id": entity_id,
        },
    )

    graph_repo = GraphRepository(neo4j_driver)
    try:
        result = await graph_repo.get_entity(
            entity_id=entity_id,
            investigation_id=investigation_id,
        )
    except KeyError as exc:
        raise EntityNotFoundError(
            f"Entity {entity_id!r} not found in investigation {investigation_id!r}"
        ) from exc
    except GraphUnavailableError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Entity detail query failed: %s", exc)
        raise GraphUnavailableError(
            "Neo4j is unreachable or returned an error during entity retrieval."
        ) from exc

    return SuccessResponse(data=result)
