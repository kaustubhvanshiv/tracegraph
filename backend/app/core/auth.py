"""JWT authentication and investigation ownership enforcement.

Provides two FastAPI dependencies:

- ``get_current_user`` — validates the Bearer JWT on every request; raises
  HTTP 401 (UNAUTHORIZED) for missing, expired, or malformed tokens.
- ``require_investigation_owner`` — a dependency *factory* (returns a
  Depends-able callable) that checks the authenticated caller owns the
  referenced investigation; raises HTTP 403 (FORBIDDEN) otherwise.

All cryptographic keys are loaded from ``config.py`` via Pydantic
``BaseSettings`` — no secrets are hardcoded in this module.

Requirements covered: 15.1, 15.2, 15.3, 15.4
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurrentUser:
    """Lightweight representation of the authenticated caller.

    Constructed from the JWT payload after successful verification.
    Only ``user_id`` is required for ownership checks; the full
    payload is kept for any downstream need (e.g. audit logging).
    """

    user_id: str
    payload: dict  # raw decoded claims


# ---------------------------------------------------------------------------
# Internal DB helper — isolated for testability
# ---------------------------------------------------------------------------


async def _fetch_investigation_owner(
    investigation_id: str,
    db: AsyncSession,
) -> str | None:
    """Return the ``owner_id`` for the given investigation, or ``None`` if
    the investigation does not exist.

    This is a standalone async function (not a method) so tests can easily
    replace it via ``unittest.mock.patch`` without needing a live SQLAlchemy
    engine or a working ORM model class.
    """
    # Lazy import keeps auth.py importable in environments where the
    # SQLAlchemy model registry cannot be initialised (e.g. Python 3.14
    # incompatibility with SQLAlchemy 2.0.31 used during development).
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.investigation import InvestigationModel  # noqa: PLC0415

    result = await db.execute(
        select(InvestigationModel.owner_id).where(
            InvestigationModel.investigation_id
            == investigation_id  # type: ignore[arg-type]
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# get_current_user — FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Extract and verify the Bearer JWT from the Authorization header.

    Raises:
        UnauthorizedError: if the header is missing, the token is malformed,
            expired, or the signature is invalid. Never propagates ``JWTError``
            to the caller — always converts to the application error type.

    Returns:
        CurrentUser: a validated, immutable representation of the caller.
    """
    # --- Extract token from "Bearer <token>" --------------------------------
    if not authorization:
        raise UnauthorizedError(
            "Authorization header is missing. "
            "Provide a Bearer token via the Authorization header."
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError(
            "Invalid Authorization header format. "
            "Expected: Authorization: Bearer <token>"
        )

    # --- Verify signature + claims -----------------------------------------
    try:
        payload: dict = jwt.decode(
            token,
            settings.jwt_secret_key,   # loaded from env — never hardcoded
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError:
        raise UnauthorizedError("Token has expired. Please obtain a new token.")
    except JWTError as exc:
        logger.debug("JWT verification failed: %s", exc)
        raise UnauthorizedError("Token is invalid or signature verification failed.")

    # --- Extract user identity from payload --------------------------------
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(
            "Token payload is missing the 'sub' (subject) claim."
        )

    return CurrentUser(user_id=user_id, payload=payload)


# ---------------------------------------------------------------------------
# require_investigation_owner — dependency factory
# ---------------------------------------------------------------------------


def require_investigation_owner(investigation_id: str) -> "InvestigationOwnerChecker":
    """Dependency factory for investigation ownership enforcement.

    Usage in a route handler::

        @router.get("/{investigation_id}/graph")
        async def get_graph(
            investigation_id: str,
            _: None = Depends(require_investigation_owner(investigation_id)),
        ): ...

    Args:
        investigation_id: The UUID string from the path parameter.

    Returns:
        An ``InvestigationOwnerChecker`` FastAPI-compatible callable.
    """
    return InvestigationOwnerChecker(investigation_id)


class InvestigationOwnerChecker:
    """Callable dependency that enforces investigation ownership.

    FastAPI calls ``__call__`` and injects ``db`` and ``current_user``
    automatically.  Raises ``ForbiddenError`` (HTTP 403) when the
    authenticated user does not own the investigation.

    The investigation's existence is NOT checked here for authorization
    purposes — both "not found" and "wrong owner" produce the same
    ``ForbiddenError`` to avoid leaking existence information.
    """

    def __init__(self, investigation_id: str) -> None:
        self._investigation_id = investigation_id

    async def __call__(
        self,
        db: Annotated[AsyncSession, Depends(get_db)],
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> None:
        """Verify the caller owns this investigation.

        Raises:
            ForbiddenError: if the investigation exists but is owned by
                a different user, or if the investigation does not exist
                (to avoid leaking existence information to non-owners).
        """
        owner_id = await _fetch_investigation_owner(self._investigation_id, db)

        # Treat "not found" and "wrong owner" identically to prevent
        # information leakage (a non-owner should not learn whether an
        # investigation ID exists at all).
        if owner_id is None or owner_id != current_user.user_id:
            raise ForbiddenError(
                "You do not have permission to access this investigation."
            )
