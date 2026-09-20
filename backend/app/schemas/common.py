from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Generic success envelope for API responses."""
    status: str = Field(default="success")
    data: T


class ErrorResponse(BaseModel):
    """Generic error envelope for API error responses."""
    status: str = Field(default="error")
    code: str
    message: str
    details: dict[str, Any] | None = None

