import copy
from typing import Any
from app.adapters.base import ParserAdapter
from app.schemas.parser import ParsedEvent, ParseError


class AdapterRegistry:
    """Registry that maps source_type strings to their corresponding ParserAdapter implementations."""

    def __init__(self) -> None:
        self._adapters: dict[str, ParserAdapter] = {}

    def register(self, adapter: ParserAdapter) -> None:
        """Register a ParserAdapter. Overwrites any previous adapter for the same source_type."""
        if not hasattr(adapter, "source_type") or not isinstance(adapter.source_type, str):
            raise ValueError("Adapter must have a valid string source_type attribute")
        self._adapters[adapter.source_type] = adapter

    def get_adapter(self, source_type: str) -> ParserAdapter | None:
        """Retrieve registered adapter for source_type, or None if unregistered."""
        return self._adapters.get(source_type)

    def is_registered(self, source_type: str) -> bool:
        """Check if a source_type is registered."""
        return source_type in self._adapters

    def list_source_types(self) -> list[str]:
        """Return list of all registered source_type strings."""
        return list(self._adapters.keys())

    def dispatch(self, source_type: str, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        """
        Dispatch raw event parsing to the registered adapter for source_type.

        If source_type is unregistered or raw is invalid, returns ParseError (never raises).
        """
        if not isinstance(raw, dict):
            return ParseError(
                reason="Raw event must be a dictionary",
                raw_event={} if raw is None else {"data": str(raw)}
            )

        adapter = self._adapters.get(source_type)
        if adapter is None:
            return ParseError(
                event_id=str(raw.get("event_id")) if raw.get("event_id") is not None else None,
                field_name="source_type",
                reason=f"No parser adapter registered for source_type: {source_type!r}",
                raw_event=copy.deepcopy(raw),
            )

        return adapter.parse(raw)


# Default global registry instance
default_registry = AdapterRegistry()
