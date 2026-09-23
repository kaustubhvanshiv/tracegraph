"""Analyst notes API routes.

Endpoints:
  POST /api/investigations/{investigation_id}/notes — add note (JWT + ownership)
  GET  /api/investigations/{investigation_id}/notes — list notes (JWT + ownership)

Requirements covered: 11.7, 11.8, 15.1, 15.2, 16.1, 16.4
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.common import SuccessResponse
from app.schemas.investigation import Note, NotePayload
from app.services.investigation import InvestigationService

router = APIRouter(prefix="/api/investigations", tags=["notes"])


# ---------------------------------------------------------------------------
# POST /api/investigations/{investigation_id}/notes — add note
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/notes",
    response_model=SuccessResponse[Note],
    status_code=201,
)
async def add_note(
    investigation_id: str,
    payload: NotePayload,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[Note]:
    """Add an analyst note to an investigation. Requires JWT + ownership."""
    svc = InvestigationService(db)
    note = await svc.add_note(
        investigation_id,
        note=payload,
        author_id=current_user.user_id,
    )
    return SuccessResponse(data=note)


# ---------------------------------------------------------------------------
# GET /api/investigations/{investigation_id}/notes — list notes
# ---------------------------------------------------------------------------


@router.get(
    "/{investigation_id}/notes",
    response_model=SuccessResponse[list[Note]],
)
async def list_notes(
    investigation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuccessResponse[list[Note]]:
    """Return all notes for an investigation. Requires JWT + ownership."""
    svc = InvestigationService(db)
    notes = await svc.list_notes(investigation_id, caller_id=current_user.user_id)
    return SuccessResponse(data=notes)
