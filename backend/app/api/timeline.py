"""Timeline API routes.

Endpoints:
  GET /api/investigations/{investigation_id}/timeline

Security:
  - JWT required (get_current_user dependency).
  - Investigation ownership enforced (same pattern as events.py).

Query parameters:
  start_time, end_time, entity_id, event_type, severity, limit, offset

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.errors import ForbiddenError
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.timeline import TimelineFilter, TimelineResult
from app.services.timeline import TimelineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["timeline"])


# ---------------------------------------------------------------------------
# Helper — ownership enforcement (mirrors events.py pattern)
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
# GET /api/investigations/{investigation_id}/timeline
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/timeline",
    response_model=SuccessResponse[TimelineResult],
    status_code=200,
    summary="Get chronological timeline of events for an investigation",
)
async def get_timeline(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    start_time: Annotated[
        datetime | None,
        Query(description="Filter events on or after this UTC timestamp (ISO-8601)"),
    ] = None,
    end_time: Annotated[
        datetime | None,
        Query(description="Filter events on or before this UTC timestamp (ISO-8601)"),
    ] = None,
    entity_id: Annotated[
        str | None,
        Query(description="Filter to events linked to this entity ID"),
    ] = None,
    event_type: Annotated[
        str | None,
        Query(description="Filter by event_type (e.g. authentication, process_exec)"),
    ] = None,
    severity: Annotated[
        str | None,
        Query(description="Filter by severity (low, medium, high, critical)"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=1000, description="Maximum number of events to return"),
    ] = 100,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of events to skip for pagination"),
    ] = 0,
) -> SuccessResponse[TimelineResult]:
    """Retrieve a chronologically sorted, filtered event timeline.

    Events are sorted ascending by timestamp.  Each event includes a list of
    ``entity_ids`` extracted from ``event_entity_map`` for graph cross-linking.

    Supports optional filtering by time range, entity, event type, and
    severity.  The filter-is-subset invariant is guaranteed: a filtered result
    is always a subset of the unfiltered result for the same investigation.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    filters = TimelineFilter(
        start_time=start_time,
        end_time=end_time,
        entity_id=entity_id,
        event_type=event_type,
        severity=severity,
        limit=limit,
        offset=offset,
    )

    logger.info(
        "Timeline request",
        extra={
            "investigation_id": investigation_id,
            "filters": {
                "start_time": str(start_time) if start_time else None,
                "end_time": str(end_time) if end_time else None,
                "entity_id": entity_id,
                "event_type": event_type,
                "severity": severity,
                "limit": limit,
                "offset": offset,
            },
        },
    )

    svc = TimelineService(db=db)
    result = await svc.get_timeline(
        investigation_id=investigation_id,
        filters=filters,
    )

    return SuccessResponse(data=result)
