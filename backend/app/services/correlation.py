"""Temporal correlation engine.

Evaluates candidate pairs against seven named signals:
  shared_user, shared_host, shared_ip, host_continuity,
  temporal_proximity, compatible_action_sequence, process_file_context

combined_score = sum(fired weights) / sum(ALL weights)
NOTE: combined_score is a weighted-sum relevance indicator and is NOT an
attack probability score.

Signal weights are loaded from config, not hardcoded.

Full implementation is covered by task 11.1.
"""

# TODO: implement — task 11.1
