"""AI summary API routes.

Endpoints (implemented in task 20.2):
  POST /api/investigations/{id}/summary
  GET  /api/investigations/{id}/summary
"""

from fastapi import APIRouter

# TODO: implement — task 20.2

router = APIRouter(prefix="/api/investigations", tags=["summary"])
