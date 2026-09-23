from typing import Any, Protocol, runtime_checkable
from app.schemas.parser import ParsedEvent, ParseError


@runtime_checkable
class ParserAdapter(Protocol):
    """Protocol that all log source-type adapters must implement."""
    source_type: str

    def parse(self, raw: dict[str, Any]) -> ParsedEvent | ParseError:
        """
        Transform raw event log dict into a ParsedEvent or ParseError.

        Preconditions:
          - raw is a non-empty dict containing event telemetry
        Postconditions:
          - Returns ParsedEvent with recognized fields mapped
          - Unrecognized fields are preserved in extra_fields
          - Never raises exceptions; returns ParseError on malformed input
          - Does NOT mutate the input raw dict
          - Preserves event_id unchanged
        """
        ...

