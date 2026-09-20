"""ParserAdapter Protocol definition.

All source-type adapters must implement this protocol.

Preconditions (documented as per design):
  - raw is a non-empty dict with at least a timestamp field
Postconditions:
  - Returns ParsedEvent with all recognized fields populated
  - Unrecognized fields are preserved in extra_fields
  - Never raises; returns ParseError on failure
  - Does NOT mutate the input raw dict
  - Preserves event_id unchanged

Full implementation is covered by task 5.1.
"""

# TODO: implement — task 5.1
# class ParserAdapter(Protocol):
#     source_type: str
#     def parse(self, raw: dict) -> ParsedEvent | ParseError: ...
