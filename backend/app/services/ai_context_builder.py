"""AI context builder.

Assembles a bounded, structured InvestigationContext from graph, timeline,
and evidence data.  Applies configurable size limits; prioritizes high/critical
severity events and most-connected events when sampling.

Never includes secrets, credentials, or PII beyond normalized event fields.
Produces a fully JSON-serializable context with no circular references.

Full implementation is covered by task 19.1.
"""

# TODO: implement — task 19.1
