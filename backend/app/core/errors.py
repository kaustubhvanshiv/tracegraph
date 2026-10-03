"""Standard error codes, application exception classes, and FastAPI error handlers.

Error code constants map 1:1 to HTTP status codes via the exception classes below.
The global handler converts any AppError subclass to an ErrorResponse JSON envelope.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------

VALIDATION_ERROR = "VALIDATION_ERROR"
INVALID_SOURCE_TYPE = "INVALID_SOURCE_TYPE"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
INVESTIGATION_NOT_FOUND = "INVESTIGATION_NOT_FOUND"
EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
PARSE_ERROR = "PARSE_ERROR"
AI_UNAVAILABLE = "AI_UNAVAILABLE"
GRAPH_UNAVAILABLE = "GRAPH_UNAVAILABLE"

# ---------------------------------------------------------------------------
# Base application exception
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base class for all application-level exceptions.

    Every subclass sets a default ``http_status`` and ``code`` so callers only
    need to pass a human-readable ``message`` (and optional ``details``).
    """

    code: str = VALIDATION_ERROR
    http_status: int = 422

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


# ---------------------------------------------------------------------------
# Concrete exception classes — one per error code
# ---------------------------------------------------------------------------


class ValidationError(AppError):
    """Input failed schema or business-rule validation."""

    code = VALIDATION_ERROR
    http_status = 422


class InvalidSourceTypeError(AppError):
    """The provided source_type is not registered in the adapter registry."""

    code = INVALID_SOURCE_TYPE
    http_status = 422


class UnauthorizedError(AppError):
    """JWT token is missing, expired, or invalid."""

    code = UNAUTHORIZED
    http_status = 401


class ForbiddenError(AppError):
    """Authenticated user does not own (or have access to) the requested resource."""

    code = FORBIDDEN
    http_status = 403


class InvestigationNotFoundError(AppError):
    """The requested investigation does not exist."""

    code = INVESTIGATION_NOT_FOUND
    http_status = 404


class EventNotFoundError(AppError):
    """The requested security event does not exist within this investigation."""

    code = EVENT_NOT_FOUND
    http_status = 404


class EntityNotFoundError(AppError):
    """The requested graph entity does not exist within this investigation."""

    code = ENTITY_NOT_FOUND
    http_status = 404


class ParseError(AppError):
    """A parser adapter returned a hard failure for the given raw event."""

    code = PARSE_ERROR
    http_status = 422


class AIUnavailableError(AppError):
    """The configured LLM provider is unreachable or returned an unrecoverable error."""

    code = AI_UNAVAILABLE
    http_status = 503


class GraphUnavailableError(AppError):
    """Neo4j is unreachable or returned a connection-level error."""

    code = GRAPH_UNAVAILABLE
    http_status = 503


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------


def _error_response_body(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict:
    """Build the ErrorResponse JSON dict without importing the Pydantic schema
    to avoid circular imports between core and schemas packages."""
    body: dict[str, Any] = {"status": "error", "code": code, "message": message}
    if details is not None:
        body["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to *app*.

    Call this once, after adding middleware, in app/main.py.
    """

    @app.exception_handler(GraphUnavailableError)
    async def graph_unavailable_handler(
        request: Request, exc: GraphUnavailableError
    ) -> JSONResponse:
        """Return HTTP 503 when Neo4j is unreachable (Requirement 16.5)."""
        return JSONResponse(
            status_code=503,
            content=_error_response_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Convert any AppError subclass to the ErrorResponse envelope (Req 16.1, 16.2)."""
        return JSONResponse(
            status_code=exc.http_status,
            content=_error_response_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic request validation errors to HTTP 422 with VALIDATION_ERROR code."""
        # Summarise Pydantic's error list into a human-readable message.
        first = exc.errors()[0] if exc.errors() else {}
        loc = " -> ".join(str(p) for p in first.get("loc", []))
        msg = first.get("msg", "Request validation failed")
        detail_message = f"{loc}: {msg}" if loc else msg

        return JSONResponse(
            status_code=422,
            content=_error_response_body(
                code=VALIDATION_ERROR,
                message=detail_message,
                details={"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all handler — never expose stack traces to the client."""
        return JSONResponse(
            status_code=500,
            content=_error_response_body(
                code="INTERNAL_ERROR",
                message="An unexpected internal error occurred.",
            ),
        )
