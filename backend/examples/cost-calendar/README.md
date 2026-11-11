# Synthetic saved cost calendar requests

Replace the illustrative product ID with an owned product and use a fresh
conversation request UUID. POST request.json to
/api/v1/products/{product_id}/cost-calendar with a current seller session.
This deterministic read-only report works without AI and excludes the current
incomplete UTC month. A new product can correctly show insufficient history.

With the existing local assistant enabled, POST conversation.json to
/api/v1/assistants/conversations. Ask about the saved annual differences, then
why they do not prove seasonal effects, inflation or future prices. Display
exact facts separately from model prose and distinguish unknown from recorded zero.

These are request shapes, not actual historical price claims. Any populated
mock calendar must be labelled synthetic and kept out of real seller evidence.
See [the contract and frontend handoff](../../../docs/saved-cost-calendar.md).
