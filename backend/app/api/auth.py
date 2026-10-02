"""Authentication API — JWT token issuance.

Provides a single endpoint:
    POST /api/auth/token  — issue a signed JWT for a given username.

This is a development-grade implementation: it accepts any non-empty username
with no password check.  For a production deployment, replace the body of
``issue_token`` with a real credential verification step.

Requirements covered: 15.1 (JWT-protected API surface)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from jose import jwt
from pydantic import BaseModel, Field

from app.core.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TokenRequest(BaseModel):
    """Credentials for token issuance."""
    username: str = Field(min_length=1, description="Analyst username (any non-empty string)")


class TokenResponse(BaseModel):
    """Issued JWT and its metadata."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int       # seconds until expiry
    username: str


# ---------------------------------------------------------------------------
# POST /api/auth/token
# ---------------------------------------------------------------------------


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest) -> TokenResponse:
    """Issue a signed JWT access token for the given username.

    The token payload contains:
    - ``sub``: the username (used as user_id throughout the app)
    - ``exp``: expiry timestamp (controlled by JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    - ``iat``: issued-at timestamp

    No password verification is performed — this is a development convenience
    endpoint.  Replace with real credential checking before production use.
    """
    expire_minutes = settings.jwt_access_token_expire_minutes
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)

    payload = {
        "sub": body.username,
        "iat": now,
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expire_minutes * 60,
        username=body.username,
    )
