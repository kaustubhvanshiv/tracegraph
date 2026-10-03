"""AI summary API routes.

Endpoints (implemented in task 20.2):
  POST /api/investigations/{id}/summary
  GET  /api/investigations/{id}/summary

Security:
  - JWT required (get_current_user dependency).
  - Investigation ownership enforced (same pattern as events.py).

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
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.common import SuccessResponse
from app.schemas.summary import SummaryResult
from app.services.ai_context_builder import AIContextBuilder
from app.services.ai_summary import get_ai_summary_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/investigations", tags=["summary"])


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
# POST /api/investigations/{investigation_id}/summary — generate/refresh summary
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/summary",
    response_model=SuccessResponse[SummaryResult],
    status_code=200,
    summary="Generate or force-refresh AI summary",
)
async def generate_summary(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
    force_refresh: Annotated[
        bool,
        Query(description="Bypass cache and regenerate summary"),
    ] = False,
) -> SuccessResponse[SummaryResult]:
    """Generate an AI-powered narrative summary for the investigation.

    If a cached summary exists and ``force_refresh`` is false, returns the
    cached version.  Otherwise, builds a fresh context and calls the LLM.

    Returns AI_UNAVAILABLE (503) when the LLM is unreachable; other panels
    must remain functional.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Summary generation request",
        extra={
            "investigation_id": investigation_id,
            "force_refresh": force_refresh,
        },
    )

    # Build context
    try:
        context_builder = AIContextBuilder(db=db, neo4j_driver=neo4j_driver)
        context = await context_builder.build_context(investigation_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build AI context: %s", exc)
        raise AIUnavailableError("AI context builder unavailable") from exc

    # Get the summary service
    summary_service = get_ai_summary_service()

    # Generate summary
    try:
        result = await summary_service.generate_summary(context, force_refresh)
    except Exception as exc:  # noqa: BLE001
        logger.error("Summary generation failed: %s", exc)
        raise AIUnavailableError("AI summary service unavailable") from exc

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/summary — retrieve cached summary
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/summary",
    response_model=SuccessResponse[SummaryResult],
    status_code=200,
    summary="Retrieve cached AI summary",
)
async def get_summary(
    investigation_id: Annotated[str, Path(description="Target investigation ID")],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    neo4j_driver: Annotated[AsyncDriver, Depends(get_neo4j_driver)],
) -> SuccessResponse[SummaryResult]:
    """Retrieve the cached AI summary for an investigation.

    Returns the most recently generated summary.  If no summary has been
    generated yet, builds a fresh context and generates one.
    """
    await _check_investigation_ownership(investigation_id, current_user, db)

    logger.info(
        "Summary retrieval request",
        extra={"investigation_id": investigation_id},
    )

    # Build context and generate summary (will use cache if available)
    try:
        context_builder = AIContextBuilder(db=db, neo4j_driver=neo4j_driver)
        context = await context_builder.build_context(investigation_id)
        summary_service = get_ai_summary_service()
        result = await summary_service.generate_summary(context, force_refresh=False)
    except Exception as exc:  # noqa: BLE001
        logger.error("Summary retrieval failed: %s", exc)
        raise AIUnavailableError("AI summary service unavailable") from exc

    return SuccessResponse(data=result)