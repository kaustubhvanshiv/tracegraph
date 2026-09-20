"""PostgreSQL event repository.

Uses ON CONFLICT DO NOTHING for idempotent re-ingestion.
All queries use parameterized SQLAlchemy — no string interpolation.

Methods (implemented in task 14.2):
  store(events, investigation_id, entity_map)
  get(event_id, investigation_id)
  Also inserts into event_entity_map for timeline cross-linking.

Full implementation is covered by task 14.2.
"""

# TODO: implement — task 14.2
