"""SQLAlchemy ORM model for the security_events table.

Full implementation (including source_type column, composite unique key on
event_id + investigation_id, and all indexes) is covered by task 2.2.
"""

# TODO: implement — task 2.2
# Table: security_events
# Columns: id (serial PK), event_id, investigation_id, source_type,
#   timestamp, event_type, action, user, source_host, destination_host,
#   source_ip, destination_ip, process, file, severity, raw_data (JSONB)
# Unique: (event_id, investigation_id)
