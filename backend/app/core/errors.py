"""Standard error codes and application exception classes.

Every error code constant here maps to an HTTP status code that is used by the
global exception handler in app.main (see task 3 for the full handler
implementation).
"""

# ---------------------------------------------------------------------------
# Error code constants
# ---------------------------------------------------------------------------

VALIDATION_ERROR = "VALIDATION_ERROR"
INVALID_SOURCE_TYPE = "INVALID_SOURCE_TYPE"
UNAUTHORIZED = "UNAUTHORIZED"
FORBIDDEN = "FORBIDDEN"
INVESTIGATION_NOT_FOUND = "INVESTIGATION_NOT_FOUND"
EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
PARSE_ERROR = "PARSE_ERROR"
AI_UNAVAILABLE = "AI_UNAVAILABLE"
GRAPH_UNAVAILABLE = "GRAPH_UNAVAILABLE"

# TODO: implement — global FastAPI exception handler that converts these codes
# to ErrorResponse JSON with the correct HTTP status (task 3)
