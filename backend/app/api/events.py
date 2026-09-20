"""Evidence ingestion API routes.

Endpoints (implemented in task 14.3):
  POST /api/investigations/{id}/events
  POST /api/investigations/{id}/events/batch
"""

from fastapi import APIRouter

# TODO: implement — task 14.3

router = APIRouter(prefix="/api/investigations", tags=["events"])
