"""Analyst notes API routes.

Endpoints (implemented in task 7.2):
  POST /api/investigations/{id}/notes
  GET  /api/investigations/{id}/notes
"""

from fastapi import APIRouter

# TODO: implement — task 7.2

router = APIRouter(prefix="/api/investigations", tags=["notes"])
