"""Investigation management API routes.

Endpoints:
  POST   /api/investigations            — create investigation (JWT required)
  GET    /api/investigations            — paginated list (JWT required)
  GET    /api/investigations/{id}       — get single (JWT + ownership)
  PATCH  /api/investigations/{id}       — update status/outcome (JWT + ownership)

Requirements covered: 11.1–11.8, 15.1, 15.2, 16.1, 16.4
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user, require_investigation_owner
from app.core.database import get_db
from app.core.errors import ValidationError
from app.schemas.common import SuccessResponse
from app.schemas.investigation import (
    CreateInvestigationPayload,
    Investigation,
    InvestigationFilter,
    InvestigationStatus,
    PatchInvestigationPayload,
)
from app.services.investigation import InvestigationService

router = APIRouter(prefix="/api/investigations", tags=["investigations"])


# ---------------------------------------------------------------------------
# POST /api/investigations — create
# ---------------------------------------------------------------------------


@router.post("", response_model=SuccessResponse[Investigation], status_code=201)
async def create_investigation(
    payload: CreateInvestigationPayload,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[Investigation]:
    """Create a new investigation. Any authenticated user may create one."""
    svc = InvestigationService(db)
    investigation = await svc.create(payload, owner_id=current_user.user_id)
    return SuccessResponse(data=investigation)


# ---------------------------------------------------------------------------
# GET /api/investigations — paginated list
# ---------------------------------------------------------------------------


@router.get("", response_model=SuccessResponse[list[Investigation]])
async def list_investigations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: InvestigationStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[list[Investigation]]:
    """Return a paginated list of investigations owned by the caller."""
    svc = InvestigationService(db)
    filters = InvestigationFilter(status=status, limit=limit, offset=offset)
    investigations = await svc.list(filters, caller_id=current_user.user_id)
    return SuccessResponse(data=investigations)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id} — get single
# ---------------------------------------------------------------------------


@router.get("/{investigation_id}", response_model=SuccessResponse[Investigation])
async def get_investigation(
    investigation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[Investigation]:
    """Retrieve a single investigation. Requires JWT + ownership (403 if not owner)."""
    # Ownership is enforced inside InvestigationService.get — raises ForbiddenError
    # for wrong owner and InvestigationNotFoundError for missing investigations.
    # The require_investigation_owner dependency also enforces 403 but is redundant
    # here since the service layer covers it, preventing double-DB-lookup.
    svc = InvestigationService(db)
    investigation = await svc.get(investigation_id, caller_id=current_user.user_id)
    return SuccessResponse(data=investigation)


# ---------------------------------------------------------------------------
# PATCH /api/investigations/{investigation_id} — update status / outcome
# ---------------------------------------------------------------------------


@router.patch("/{investigation_id}", response_model=SuccessResponse[Investigation])
async def patch_investigation(
    investigation_id: str,
    payload: PatchInvestigationPayload,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[Investigation]:
    """Update investigation status and/or record an outcome.

    Requires JWT + ownership. At least one of ``status`` or ``outcome`` must
    be provided.
    """
    if payload.status is None and payload.outcome is None:
        raise ValidationError(
            "At least one of 'status' or 'outcome' must be provided in the request body."
        )

    svc = InvestigationService(db)

    # Apply status transition first (if requested)
    if payload.status is not None:
        investigation = await svc.update_status(
            investigation_id,
            new_status=payload.status,
            caller_id=current_user.user_id,
        )
    else:
        investigation = await svc.get(investigation_id, caller_id=current_user.user_id)

    # Apply outcome recording (if requested)
    if payload.outcome is not None:
        investigation = await svc.record_outcome(
            investigation_id,
            outcome=payload.outcome,
            caller_id=current_user.user_id,
        )

    return SuccessResponse(data=investigation)
