"""SQLAlchemy ORM model for the investigations table.

Full implementation (with all CHECK constraints and indexes) is covered by
task 2.2.
"""

# TODO: implement — task 2.2
# Table: investigations
# Columns: investigation_id (UUID PK), title, description, status CHECK
#   (OPEN/UNDER_REVIEW/CLOSED), outcome CHECK, created_at, updated_at,
#   owner_id, event_count
