"""Evidence ingestion and detail API routes.

Endpoints:
  POST /api/investigations/{investigation_id}/events
  POST /api/investigations/{investigation_id}/events/batch
  GET  /api/investigations/{investigation_id}/events/{event_id}

Security:
  - JWT required on all endpoints (get_current_user dependency).
  - Investigation ownership enforced inside the handler (ForbiddenError if
    not owner, which the global error handler converts to HTTP 403).

Logging:
  - Only event_id and investigation_id are logged at INFO level.
  - Raw event data is NEVER written to logs (Req 15.5).

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 10.1–10.6,
              15.1, 15.2, 15.5, 16.1, 16.2, 16.3, 16.4
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from neo4j import AsyncDriver  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.core.errors import ForbiddenError
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.ingestion import IngestionResponse, RawEventPayload
from app.schemas.summary import EvidenceDetail
from app.services.evidence import EvidenceDetailService
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["events"])


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
# POST /api/investigations/{investigation_id}/events  — single event
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/events",
    response_model=SuccessResponse[IngestionResponse],
    status_code=200,
    summary="Ingest a single security event",
)
async def ingest_single_event(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    payload: RawEventPayload,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[IngestionResponse]:
    """Ingest a single raw security event into the investigation pipeline.

    The event is parsed, normalized, entities and relationships are extracted,
    and the result is persisted to both Neo4j (graph) and PostgreSQL (event
    store).

    Returns an ``IngestionResponse`` indicating whether the event was accepted
    or rejected (with a reason if rejected).
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Ingesting single event",
        extra={"investigation_id": investigation_id, "source_type": payload.source_type},
    )

    svc = IngestionService(db=db, neo4j_driver=neo4j_driver)
    result = await svc.process_event_batch(
        raw_events=[payload.raw],
        investigation_id=investigation_id,
        source_type=payload.source_type,
    )

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# POST /api/investigations/{investigation_id}/events/batch  — batch events
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/events/batch",
    response_model=SuccessResponse[IngestionResponse],
    status_code=200,
    summary="Ingest a batch of security events",
)
async def ingest_event_batch(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    payloads: list[RawEventPayload],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[IngestionResponse]:
    """Ingest a batch of raw security events.

    All events in the batch must share the same ``source_type``.  The first
    event in the list determines the adapter used; a mismatch inside the list
    produces per-event parse errors (not a hard failure).

    Partial-batch semantics apply: events that fail parsing or normalization
    are reported in ``errors`` without stopping the rest of the batch.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    # Group by source_type: all payloads in one batch must share the same
    # source_type to keep the pipeline simple.  If they don't, we still process
    # them one sub-batch at a time and merge the results.
    from collections import defaultdict  # noqa: PLC0415

    groups: dict[str, list] = defaultdict(list)
    for p in payloads:
        groups[p.source_type].append(p.raw)

    total_accepted = 0
    total_rejected = 0
    all_errors = []

    for source_type, raws in groups.items():
        logger.info(
            "Ingesting batch",
            extra={
                "investigation_id": investigation_id,
                "source_type": source_type,
                "count": len(raws),
            },
        )

        svc = IngestionService(db=db, neo4j_driver=neo4j_driver)
        result = await svc.process_event_batch(
            raw_events=raws,
            investigation_id=investigation_id,
            source_type=source_type,
        )

        total_accepted += result.accepted
        total_rejected += result.rejected
        all_errors.extend(result.errors)

    return SuccessResponse(
        data=IngestionResponse(
            accepted=total_accepted,
            rejected=total_rejected,
            errors=all_errors,
        )
    )


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/events/{event_id} — evidence detail
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/events/{event_id}",
    response_model=SuccessResponse[EvidenceDetail],
    status_code=200,
    summary="Get full evidence detail for a single event",
)
async def get_evidence_detail(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    event_id: Annotated[str, Path(description="Target event ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[EvidenceDetail]:
    """Retrieve the full evidence record for a single event.

    Includes:
      - Normalized SecurityEvent fields
      - Original raw_data
      - All extracted entities
      - All relationships referencing the event_id
      - Correlation metadata (signal names, combined score, explanation)

    Enforces investigation isolation: never returns data belonging to a
    different investigation.

    Returns HTTP 404 with EVENT_NOT_FOUND if event_id does not exist.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Evidence detail request",
        extra={"investigation_id": investigation_id, "event_id": event_id},
    )

    svc = EvidenceDetailService(db=db, neo4j_driver=neo4j_driver)
    try:
        result = await svc.get_evidence(event_id, investigation_id)
    except KeyError as exc:
        from app.core.errors import EventNotFoundError

        raise EventNotFoundError(str(exc)) from exc

    return SuccessResponse(data=result)
