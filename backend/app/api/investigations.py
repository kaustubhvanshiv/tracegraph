"""Investigation management API routes.

Endpoints (implemented in task 7.2):
  POST   /api/investigations
  GET    /api/investigations
  GET    /api/investigations/{id}
  PATCH  /api/investigations/{id}
"""

from fastapi import APIRouter

# TODO: implement — task 7.2

router = APIRouter(prefix="/api/investigations", tags=["investigations"])
