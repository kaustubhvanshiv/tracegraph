"""Evidence detail service.

Returns the full evidence record for a single event:
  - Normalized SecurityEvent fields
  - Original raw_data
  - All extracted entities
  - All relationships referencing the event_id
  - Correlation metadata (signals, score, explanation)

Enforces investigation isolation — never returns data from a different
investigation.

Full implementation is covered by task 16.1.
"""

# TODO: implement — task 16.1
