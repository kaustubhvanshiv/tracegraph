"""Neo4j graph repository.

Idempotent upsert semantics using MERGE patterns (parameterized Cypher only —
no string interpolation of user-controlled values).

Methods (implemented in task 13.1):
  upsert_entity, upsert_relationship, get_graph, pivot, get_entity

Returns GRAPH_UNAVAILABLE error when Neo4j is unreachable (never silently
succeeds).

Full implementation is covered by task 13.1.
"""

# TODO: implement — task 13.1
