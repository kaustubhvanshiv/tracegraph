"""Property 17: Authorization Isolation

Every request by a non-owner of an investigation receives HTTP 403 FORBIDDEN.
No investigation-scoped resource is accessible to a user other than its owner
(absent an explicit grant — which TraceGraph does not yet implement).

**Property 17: Authorization Isolation**
  ∀ request by user U for investigation owned by user V (U ≠ V):
      response raises ForbiddenError (HTTP 403, code=FORBIDDEN)

**Validates: Requirements 15.2, 11.8**

Test approach
-------------
The ownership check lives in ``InvestigationOwnerChecker.__call__``.
Rather than standing up a live PostgreSQL instance, we patch the internal
``_fetch_investigation_owner`` helper (the sole DB call) with a coroutine
that returns a caller-controlled ``stored_owner_id``.

``hypothesis`` generates (owner_id, requester_id) pairs to exercise the
property across hundreds of random inputs — ensuring isolation holds
universally, not just for a handful of hand-picked examples.

Note on hypothesis + pytest-asyncio
------------------------------------
``hypothesis`` and ``pytest-asyncio`` do not compose well in auto mode:
``@given`` wraps the test synchronously but ``pytest-asyncio`` expects a
coroutine.  The property tests are therefore plain synchronous functions
that drive ``asyncio.run()`` internally.  The unit test class methods use
``@pytest.mark.asyncio`` normally because they are not ``@given``-decorated.
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.core.auth import CurrentUser, InvestigationOwnerChecker
from app.core.errors import ForbiddenError


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Generate plausible user IDs — non-empty strings of letters, digits, and
# common separators.  Empty strings are excluded to keep the focus on
# ownership logic rather than empty-value edge cases.
user_id_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),  # letters + digits
        whitelist_characters="-_.",
    ),
    min_size=1,
    max_size=64,
)

# Generate investigation IDs as UUIDs (the canonical form) or arbitrary
# non-empty strings (to cover unusual but valid path-parameter values).
investigation_id_strategy = st.one_of(
    st.uuids().map(str),
    st.text(
        min_size=1,
        max_size=64,
        alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-",
        ),
    ),
)


def _distinct_user_ids() -> st.SearchStrategy[tuple[str, str]]:
    """Strategy producing (owner_id, requester_id) pairs where they differ."""
    return st.tuples(user_id_strategy, user_id_strategy).filter(
        lambda pair: pair[0] != pair[1]
    )


# ---------------------------------------------------------------------------
# Patching helper
# ---------------------------------------------------------------------------

_FETCH_OWNER_PATH = "app.core.auth._fetch_investigation_owner"


def _patch_owner(stored_owner_id: str | None):
    """Patch ``_fetch_investigation_owner`` to return ``stored_owner_id``."""
    mock = AsyncMock(return_value=stored_owner_id)
    return patch(_FETCH_OWNER_PATH, mock)


# ---------------------------------------------------------------------------
# Property test — non-owner always gets 403
# ---------------------------------------------------------------------------


@given(
    investigation_id=investigation_id_strategy,
    user_pair=_distinct_user_ids(),
)
@settings(
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_non_owner_always_gets_forbidden(
    investigation_id: str,
    user_pair: tuple[str, str],
) -> None:
    """Property 17: Authorization Isolation.

    For any investigation owned by ``owner_id``, a request by a different
    ``requester_id`` MUST raise ``ForbiddenError``.

    **Validates: Requirements 15.2, 11.8**
    """
    owner_id, requester_id = user_pair
    assert owner_id != requester_id

    async def _run() -> None:
        checker = InvestigationOwnerChecker(investigation_id)
        db = AsyncMock()  # not called — patched below
        requester = CurrentUser(user_id=requester_id, payload={"sub": requester_id})

        with _patch_owner(owner_id):
            with pytest.raises(ForbiddenError) as exc_info:
                await checker(db=db, current_user=requester)

        assert exc_info.value.http_status == 403
        assert exc_info.value.code == "FORBIDDEN"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property test — owner is always permitted (no ForbiddenError)
# ---------------------------------------------------------------------------


@given(
    investigation_id=investigation_id_strategy,
    owner_id=user_id_strategy,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_owner_is_never_forbidden(
    investigation_id: str,
    owner_id: str,
) -> None:
    """The owner of an investigation must NEVER receive a ForbiddenError.

    This is the complementary property: when ownership is confirmed,
    ``__call__`` returns ``None`` without raising.
    """
    async def _run() -> None:
        checker = InvestigationOwnerChecker(investigation_id)
        db = AsyncMock()
        owner = CurrentUser(user_id=owner_id, payload={"sub": owner_id})

        with _patch_owner(owner_id):
            result = await checker(db=db, current_user=owner)

        assert result is None

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Property test — missing investigation always gets 403 (information hiding)
# ---------------------------------------------------------------------------


@given(
    investigation_id=investigation_id_strategy,
    requester_id=user_id_strategy,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_missing_investigation_always_forbidden(
    investigation_id: str,
    requester_id: str,
) -> None:
    """When an investigation does not exist, any requester gets ForbiddenError.

    This prevents non-owners from distinguishing "does not exist" from
    "exists but you don't own it" — a basic information-hiding control.
    """
    async def _run() -> None:
        checker = InvestigationOwnerChecker(investigation_id)
        db = AsyncMock()
        requester = CurrentUser(user_id=requester_id, payload={"sub": requester_id})

        # DB returns None → investigation does not exist
        with _patch_owner(None):
            with pytest.raises(ForbiddenError) as exc_info:
                await checker(db=db, current_user=requester)

        assert exc_info.value.http_status == 403
        assert exc_info.value.code == "FORBIDDEN"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Unit tests for get_current_user
# ---------------------------------------------------------------------------


class TestGetCurrentUserUnit:
    """Unit tests for ``get_current_user`` covering token validation edge cases."""

    @pytest.mark.asyncio
    async def test_missing_authorization_header_raises_401(self):
        from app.core.auth import get_current_user
        from app.core.errors import UnauthorizedError

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(authorization=None)

        assert exc_info.value.http_status == 401
        assert exc_info.value.code == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_non_bearer_scheme_raises_401(self):
        from app.core.auth import get_current_user
        from app.core.errors import UnauthorizedError

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(authorization="Basic dXNlcjpwYXNz")

        assert exc_info.value.http_status == 401

    @pytest.mark.asyncio
    async def test_malformed_token_raises_401(self):
        from app.core.auth import get_current_user
        from app.core.errors import UnauthorizedError

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(authorization="Bearer not.a.valid.jwt")

        assert exc_info.value.http_status == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_current_user(self):
        """A properly signed JWT with a 'sub' claim must return a CurrentUser."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.core.auth import CurrentUser, get_current_user
        from app.core.config import settings

        payload = {
            "sub": "user-abc-123",
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        user = await get_current_user(authorization=f"Bearer {token}")

        assert isinstance(user, CurrentUser)
        assert user.user_id == "user-abc-123"

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """An expired JWT must raise UnauthorizedError, not propagate JWTError."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.core.auth import get_current_user
        from app.core.config import settings
        from app.core.errors import UnauthorizedError

        payload = {
            "sub": "user-xyz",
            "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=1),
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")

        assert exc_info.value.http_status == 401
        assert "expired" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_token_without_sub_claim_raises_401(self):
        """A valid-signature JWT missing 'sub' must raise UnauthorizedError."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.core.auth import get_current_user
        from app.core.config import settings
        from app.core.errors import UnauthorizedError

        payload = {
            # no "sub" field
            "exp": datetime.now(tz=timezone.utc) + timedelta(hours=1),
            "custom": "data",
        }
        token = jose_jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        with pytest.raises(UnauthorizedError) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")

        assert exc_info.value.http_status == 401
        assert "sub" in exc_info.value.message


# ---------------------------------------------------------------------------
# Unit tests for InvestigationOwnerChecker
# ---------------------------------------------------------------------------


class TestOwnerCheckerUnit:
    """Unit tests for ``InvestigationOwnerChecker`` direct call behaviour."""

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_requester_is_not_owner(self):
        checker = InvestigationOwnerChecker(str(uuid.uuid4()))
        db = AsyncMock()
        requester = CurrentUser(user_id="requester-B", payload={"sub": "requester-B"})

        with _patch_owner("owner-A"):
            with pytest.raises(ForbiddenError) as exc_info:
                await checker(db=db, current_user=requester)

        assert exc_info.value.http_status == 403
        assert exc_info.value.code == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_returns_none_when_requester_is_owner(self):
        checker = InvestigationOwnerChecker(str(uuid.uuid4()))
        db = AsyncMock()
        owner = CurrentUser(user_id="owner-A", payload={"sub": "owner-A"})

        with _patch_owner("owner-A"):
            result = await checker(db=db, current_user=owner)

        assert result is None

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_investigation_does_not_exist(self):
        checker = InvestigationOwnerChecker(str(uuid.uuid4()))
        db = AsyncMock()
        requester = CurrentUser(user_id="any-user", payload={"sub": "any-user"})

        with _patch_owner(None):
            with pytest.raises(ForbiddenError) as exc_info:
                await checker(db=db, current_user=requester)

        assert exc_info.value.http_status == 403
        assert exc_info.value.code == "FORBIDDEN"
