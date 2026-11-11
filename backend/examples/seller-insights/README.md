# Synthetic seller insight requests

Replace the illustrative product ID and request UUID with an owned product and
fresh request UUID. Do not use real financial or payment data in demo fixtures.

POST report-request.json to /api/v1/products/{product_id}/insights with a current
seller bearer session. This deterministic report does not require AI enabled.
It returns current modeled price warnings and closed-period recorded evidence;
it never changes business records or sends notifications.

With the existing local assistant enabled, POST conversation-request.json to
/api/v1/assistants/conversations, then use its ID to submit ordinary saved turns.
Ask what the opportunities mean, then why they do not prove avoidable waste or
guaranteed savings. Display calculated facts separately from qualitative prose.
Existing source changes hide stale answers and refresh the next turn's evidence.

See [the contract, source bounds and frontend handoff](../../../docs/seller-insights.md).
