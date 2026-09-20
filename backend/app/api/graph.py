"""Graph query API routes.

Endpoints (implemented in task 17.1):
  GET /api/investigations/{id}/graph
  GET /api/investigations/{id}/graph/pivot
  GET /api/investigations/{id}/entities/{eid}
"""

from fastapi import APIRouter

# TODO: implement — task 17.1

router = APIRouter(prefix="/api/investigations", tags=["graph"])
