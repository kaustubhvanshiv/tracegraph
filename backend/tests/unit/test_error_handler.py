"""Unit tests for global error handling middleware and error code constants.

Covers:
- Each error code maps to the correct HTTP status (Requirement 16.2)
- ErrorResponse envelope shape matches the schema (Requirements 16.1, 16.2)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    AI_UNAVAILABLE,
    EVENT_NOT_FOUND,
    FORBIDDEN,
    GRAPH_UNAVAILABLE,
    INVESTIGATION_NOT_FOUND,
    INVALID_SOURCE_TYPE,
    PARSE_ERROR,
    UNAUTHORIZED,
    VALIDATION_ERROR,
    AIUnavailableError,
    AppError,
    EventNotFoundError,
    ForbiddenError,
    GraphUnavailableError,
    InvestigationNotFoundError,
    InvalidSourceTypeError,
    ParseError,
    UnauthorizedError,
    ValidationError,
    _error_response_body,
    register_error_handlers,
)
from app.schemas.common import ErrorResponse, SuccessResponse


# ---------------------------------------------------------------------------
# Helpers — a minimal FastAPI app with one route per exception type
# ---------------------------------------------------------------------------


def build_test_app() -> FastAPI:
    """Create a throwaway FastAPI app that exposes one route per error type."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/raise/validation")
    async def raise_validation():
        raise ValidationError("bad input")

    @app.get("/raise/invalid_source_type")
    async def raise_invalid_source_type():
        raise InvalidSourceTypeError("unknown source_type: foobar")

    @app.get("/raise/unauthorized")
    async def raise_unauthorized():
        raise UnauthorizedError("JWT missing or invalid")

    @app.get("/raise/forbidden")
    async def raise_forbidden():
        raise ForbiddenError("you do not own this investigation")

    @app.get("/raise/investigation_not_found")
    async def raise_investigation_not_found():
        raise InvestigationNotFoundError("investigation abc not found")

    @app.get("/raise/event_not_found")
    async def raise_event_not_found():
        raise EventNotFoundError("event xyz not found")

    @app.get("/raise/parse_error")
    async def raise_parse_error():
        raise ParseError("failed to parse raw event")

    @app.get("/raise/ai_unavailable")
    async def raise_ai_unavailable():
        raise AIUnavailableError("LLM provider timed out")

    @app.get("/raise/graph_unavailable")
    async def raise_graph_unavailable():
        raise GraphUnavailableError("Neo4j connection refused")

    @app.get("/raise/generic")
    async def raise_generic():
        raise RuntimeError("unexpected internal error")

    @app.get("/ok")
    async def ok():
        return {"status": "success", "data": "pong"}

    return app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(build_test_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Error code constant values
# ---------------------------------------------------------------------------


class TestErrorCodeConstants:
    """Verify each constant holds the expected string value."""

    def test_validation_error_constant(self):
        assert VALIDATION_ERROR == "VALIDATION_ERROR"

    def test_invalid_source_type_constant(self):
        assert INVALID_SOURCE_TYPE == "INVALID_SOURCE_TYPE"

    def test_unauthorized_constant(self):
        assert UNAUTHORIZED == "UNAUTHORIZED"

    def test_forbidden_constant(self):
        assert FORBIDDEN == "FORBIDDEN"

    def test_investigation_not_found_constant(self):
        assert INVESTIGATION_NOT_FOUND == "INVESTIGATION_NOT_FOUND"

    def test_event_not_found_constant(self):
        assert EVENT_NOT_FOUND == "EVENT_NOT_FOUND"

    def test_parse_error_constant(self):
        assert PARSE_ERROR == "PARSE_ERROR"

    def test_ai_unavailable_constant(self):
        assert AI_UNAVAILABLE == "AI_UNAVAILABLE"

    def test_graph_unavailable_constant(self):
        assert GRAPH_UNAVAILABLE == "GRAPH_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Exception class → http_status and code attributes
# ---------------------------------------------------------------------------


class TestExceptionClassAttributes:
    """Each concrete AppError subclass carries the right code and http_status."""

    @pytest.mark.parametrize(
        "exc_class, expected_code, expected_status",
        [
            (ValidationError, VALIDATION_ERROR, 422),
            (InvalidSourceTypeError, INVALID_SOURCE_TYPE, 422),
            (UnauthorizedError, UNAUTHORIZED, 401),
            (ForbiddenError, FORBIDDEN, 403),
            (InvestigationNotFoundError, INVESTIGATION_NOT_FOUND, 404),
            (EventNotFoundError, EVENT_NOT_FOUND, 404),
            (ParseError, PARSE_ERROR, 422),
            (AIUnavailableError, AI_UNAVAILABLE, 503),
            (GraphUnavailableError, GRAPH_UNAVAILABLE, 503),
        ],
    )
    def test_exception_attributes(self, exc_class, expected_code, expected_status):
        exc = exc_class("test message")
        assert exc.code == expected_code
        assert exc.http_status == expected_status
        assert str(exc) == "test message"
        assert exc.message == "test message"

    def test_exception_accepts_details(self):
        details = {"field": "source_type", "reason": "not registered"}
        exc = ValidationError("bad field", details=details)
        assert exc.details == details

    def test_exception_details_defaults_to_none(self):
        exc = UnauthorizedError("no token")
        assert exc.details is None

    def test_all_concrete_exceptions_are_app_error_subclasses(self):
        for cls in (
            ValidationError,
            InvalidSourceTypeError,
            UnauthorizedError,
            ForbiddenError,
            InvestigationNotFoundError,
            EventNotFoundError,
            ParseError,
            AIUnavailableError,
            GraphUnavailableError,
        ):
            assert issubclass(cls, AppError)


# ---------------------------------------------------------------------------
# HTTP status code mapping via TestClient
# ---------------------------------------------------------------------------


class TestHttpStatusMapping:
    """Each error type must produce the correct HTTP status (Requirement 16.2)."""

    def test_validation_error_returns_422(self, client):
        r = client.get("/raise/validation")
        assert r.status_code == 422

    def test_invalid_source_type_returns_422(self, client):
        r = client.get("/raise/invalid_source_type")
        assert r.status_code == 422

    def test_unauthorized_returns_401(self, client):
        r = client.get("/raise/unauthorized")
        assert r.status_code == 401

    def test_forbidden_returns_403(self, client):
        r = client.get("/raise/forbidden")
        assert r.status_code == 403

    def test_investigation_not_found_returns_404(self, client):
        r = client.get("/raise/investigation_not_found")
        assert r.status_code == 404

    def test_event_not_found_returns_404(self, client):
        r = client.get("/raise/event_not_found")
        assert r.status_code == 404

    def test_parse_error_returns_422(self, client):
        r = client.get("/raise/parse_error")
        assert r.status_code == 422

    def test_ai_unavailable_returns_503(self, client):
        r = client.get("/raise/ai_unavailable")
        assert r.status_code == 503

    def test_graph_unavailable_returns_503(self, client):
        r = client.get("/raise/graph_unavailable")
        assert r.status_code == 503

    def test_unhandled_exception_returns_500(self, client):
        r = client.get("/raise/generic")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# ErrorResponse envelope shape
# ---------------------------------------------------------------------------


class TestErrorResponseEnvelopeShape:
    """Every error response must match the ErrorResponse schema (Requirement 16.1)."""

    def _assert_error_envelope(self, response, expected_code: str) -> dict:
        """Assert the response body is a valid ErrorResponse envelope and return it."""
        body = response.json()
        # Must parse without raising against the Pydantic model
        parsed = ErrorResponse(**body)
        assert parsed.status == "error"
        assert parsed.code == expected_code
        assert isinstance(parsed.message, str)
        assert len(parsed.message) > 0
        return body

    def test_unauthorized_envelope(self, client):
        r = client.get("/raise/unauthorized")
        self._assert_error_envelope(r, UNAUTHORIZED)

    def test_forbidden_envelope(self, client):
        r = client.get("/raise/forbidden")
        self._assert_error_envelope(r, FORBIDDEN)

    def test_investigation_not_found_envelope(self, client):
        r = client.get("/raise/investigation_not_found")
        self._assert_error_envelope(r, INVESTIGATION_NOT_FOUND)

    def test_event_not_found_envelope(self, client):
        r = client.get("/raise/event_not_found")
        self._assert_error_envelope(r, EVENT_NOT_FOUND)

    def test_validation_error_envelope(self, client):
        r = client.get("/raise/validation")
        self._assert_error_envelope(r, VALIDATION_ERROR)

    def test_invalid_source_type_envelope(self, client):
        r = client.get("/raise/invalid_source_type")
        self._assert_error_envelope(r, INVALID_SOURCE_TYPE)

    def test_parse_error_envelope(self, client):
        r = client.get("/raise/parse_error")
        self._assert_error_envelope(r, PARSE_ERROR)

    def test_ai_unavailable_envelope(self, client):
        r = client.get("/raise/ai_unavailable")
        self._assert_error_envelope(r, AI_UNAVAILABLE)

    def test_graph_unavailable_envelope(self, client):
        r = client.get("/raise/graph_unavailable")
        self._assert_error_envelope(r, GRAPH_UNAVAILABLE)

    def test_envelope_has_no_extra_top_level_keys_for_error_without_details(
        self, client
    ):
        r = client.get("/raise/unauthorized")
        body = r.json()
        # details is Optional — when absent, key should not appear in response
        assert "details" not in body or body["details"] is None

    def test_envelope_includes_details_when_present(self):
        """_error_response_body includes details only when they are provided."""
        body_with = _error_response_body(VALIDATION_ERROR, "bad", {"field": "x"})
        body_without = _error_response_body(VALIDATION_ERROR, "bad")
        assert body_with["details"] == {"field": "x"}
        assert "details" not in body_without

    def test_envelope_status_field_is_always_error(self, client):
        for path in (
            "/raise/validation",
            "/raise/unauthorized",
            "/raise/forbidden",
            "/raise/investigation_not_found",
            "/raise/event_not_found",
            "/raise/parse_error",
            "/raise/ai_unavailable",
            "/raise/graph_unavailable",
        ):
            body = client.get(path).json()
            assert body["status"] == "error", f"status != 'error' for {path}"

    def test_unhandled_exception_envelope_shape(self, client):
        r = client.get("/raise/generic")
        body = r.json()
        assert body["status"] == "error"
        assert "code" in body
        assert "message" in body


# ---------------------------------------------------------------------------
# FastAPI RequestValidationError → VALIDATION_ERROR 422
# ---------------------------------------------------------------------------


class TestRequestValidationError:
    """Pydantic request-validation errors are converted to the standard envelope."""

    def test_missing_required_query_param_returns_422(self):
        """A route that requires a query param returns 422 VALIDATION_ERROR."""
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/strict")
        async def strict(required_param: int):
            return {"v": required_param}

        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/strict")  # missing required_param
        assert r.status_code == 422
        body = r.json()
        assert body["status"] == "error"
        assert body["code"] == VALIDATION_ERROR
        assert "message" in body


# ---------------------------------------------------------------------------
# SuccessResponse envelope (sanity check — not an error, but related schema)
# ---------------------------------------------------------------------------


class TestSuccessResponseEnvelope:
    """SuccessResponse wraps data correctly (Requirement 16.4)."""

    def test_success_envelope_shape(self):
        resp = SuccessResponse[str](data="ok")
        assert resp.status == "success"
        assert resp.data == "ok"

    def test_success_envelope_default_status(self):
        resp = SuccessResponse[dict](data={"key": "value"})
        assert resp.status == "success"

    def test_success_response_serializes_correctly(self):
        resp = SuccessResponse[int](data=42)
        d = resp.model_dump()
        assert d == {"status": "success", "data": 42}

    def test_error_response_serializes_correctly(self):
        resp = ErrorResponse(code=UNAUTHORIZED, message="no token")
        d = resp.model_dump()
        assert d["status"] == "error"
        assert d["code"] == UNAUTHORIZED
        assert d["message"] == "no token"
        assert d["details"] is None

    def test_error_response_with_details_serializes_correctly(self):
        details = {"field": "source_type"}
        resp = ErrorResponse(
            code=INVALID_SOURCE_TYPE, message="unknown type", details=details
        )
        d = resp.model_dump()
        assert d["details"] == details
