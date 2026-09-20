"""AI summary service.

Generates evidence-grounded narrative summaries using an LLM provider
abstracted behind the LLMProvider protocol.

Anti-hallucination: system prompt prohibits inventing events, entities, or
maliciousness claims not present in context.  Post-generation validation
checks all evidence_refs exist in context.

On LLM failure: returns SummaryResult(error_flag=True) — never raises.

Caches by (investigation_id, context_hash); supports force_refresh=True.

Full implementation is covered by task 20.1.
"""

# TODO: implement — task 20.1
