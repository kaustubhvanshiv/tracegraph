"""Timeline API routes.

Endpoints (implemented in task 15.2):
  GET /api/investigations/{id}/timeline
"""

from fastapi import APIRouter

# TODO: implement — task 15.2

router = APIRouter(prefix="/api/investigations", tags=["timeline"])
