"""AI summary API routes.

Endpoints:
  POST /api/investigations/{investigation_id}/summary — generate or force-refresh summary
  GET  /api/investigations/{investigation_id}/summary — retrieve cached summary

Security:
  - JWT required (get_current_user).
  - Investigation ownership enforced.

Requirements: 13.3, 13.4, 13.5, 16.2
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from neo4j import AsyncDriver  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db, get_neo4j_driver
from app.core.errors import AIUnavailableError, ForbiddenError
from app.repositories.graph_repository import GraphRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.summary import SummaryResult
from app.services.ai_context_builder import AIContextBuilder
from app.services.ai_summary import AISummaryService
from app.services.timeline import TimelineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["summary"])

# Singleton service instance with default provider (or pluggable via app context)
_summary_service = AISummaryService()


# ---------------------------------------------------------------------------
# Helper — ownership enforcement
# ---------------------------------------------------------------------------


async def _check_investigation_ownership(
    investigation_id: str,
    current_user: CurrentUser,
    db: AsyncSession,
) -> None:
    """Raise ForbiddenError if the caller is not the investigation owner."""
    inv_repo = InvestigationRepository(db)
    row = await inv_repo.get_by_id(investigation_id)
    if row is None or str(row.owner_id) != current_user.user_id:
        raise ForbiddenError(
            "You do not have permission to access this investigation."
        )


# ---------------------------------------------------------------------------
# POST /api/investigations/{investigation_id}/summary
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/summary",
    response_model=SuccessResponse[SummaryResult],
    status_code=200,
    summary="Generate or force-refresh AI investigation summary",
)
async def generate_summary(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    force_refresh: Annotated[
        bool,
        Query(description="Bypass cache and force AI regeneration"),
    ] = False,
) -> SuccessResponse[SummaryResult]:
    """Generate or force-refresh an evidence-grounded AI narrative summary.

    Assembles context from investigation graph and timeline, executes AI summary
    service, and returns the grounded summary. If LLM service fails, returns
    HTTP 503 (AI_UNAVAILABLE).
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "AI summary generation request",
        extra={
            "investigation_id": investigation_id,
            "force_refresh": force_refresh,
        },
    )

    # 1. Fetch graph & timeline data to build context
    graph_repo = GraphRepository(neo4j_driver)
    from app.schemas.graph import GraphFilter  # noqa: PLC0415
    graph_res = await graph_repo.get_graph(investigation_id, filters=GraphFilter())

    timeline_svc = TimelineService(db)
    from app.schemas.timeline import TimelineFilter  # noqa: PLC0415
    timeline_res = await timeline_svc.get_timeline(investigation_id, filters=TimelineFilter(limit=1000))

    # 2. Build AI Context
    context_builder = AIContextBuilder()
    context = context_builder.build_context(
        investigation_id=investigation_id,
        graph=graph_res,
        timeline=timeline_res,
    )

    # 3. Generate summary
    result = await _summary_service.generate_summary(
        context=context,
        force_refresh=force_refresh,
    )

    if result.error_flag:
        logger.error("AI summary failed for %s: %s", investigation_id, result.error_message)
        raise AIUnavailableError(
            result.error_message or "AI summary service is currently unavailable."
        )

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/summary
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/summary",
    response_model=SuccessResponse[SummaryResult],
    status_code=200,
    summary="Retrieve cached AI summary for investigation",
)
async def get_summary(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[SummaryResult]:
    """Retrieve cached AI summary for an investigation.

    Returns HTTP 503 (AI_UNAVAILABLE) if no cached summary is available yet.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    result = _summary_service.get_cached_summary(investigation_id)
    if result is None:
        raise AIUnavailableError(
            f"No cached summary available for investigation {investigation_id!r}."
        )

    return SuccessResponse(data=result)
