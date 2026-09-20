"""Normalization engine: maps parsed fields to the Common Security Event Model.

Responsibilities:
  - Configurable field-name mapping tables (not hardcoded)
  - Timestamp normalization to UTC ISO-8601
  - Identifier canonicalization (hostname lowercase, IP notation, domain-strip)
  - Raw data preservation in SecurityEvent.raw_data

Full implementation is covered by task 6.1.
"""

# TODO: implement — task 6.1
