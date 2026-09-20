"""Ingestion pipeline orchestration service.

Implements the full process_event_batch algorithm:
  validate investigation → parse → normalize → validate schema
  → extract entities → extract relationships → retrieve candidates
  → correlate → upsert graph → store events + entity map

Full implementation is covered by task 14.1.
"""

# TODO: implement — task 14.1
