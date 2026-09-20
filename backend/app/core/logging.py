"""Structured JSON logging configuration.

Full implementation is covered by task 21.  At INFO level, only event_id and
investigation_id are logged for event-processing operations; raw event data is
never emitted at INFO level.
"""

import logging

# TODO: implement — configure structlog or standard-library logging to emit
# JSON-structured output and enforce the raw-data-never-at-INFO rule (task 21)

def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger by name (placeholder until task 21)."""
    return logging.getLogger(name)
