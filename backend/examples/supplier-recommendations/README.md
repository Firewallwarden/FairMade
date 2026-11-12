# Synthetic supplier review examples

Replace illustrative IDs with an owned product and one of its saved supplier
comparison reports. The report's quote snapshots are recalculated against current
input rules; no newly entered quote is silently added. Use a fresh conversation
request UUID and a current seller bearer session. No real prices are asserted.

POST request.json to /api/v1/products/{product_id}/supplier-recommendations.
The exact report works without AI. Selection is only for input review, with
finished-product Quality Locks still binding and no substitution approved.

With the existing local assistant enabled, POST conversation.json to
/api/v1/assistants/conversations. Ask why the input tradeoffs need review, then
why they do not establish certified quality or guaranteed savings. Render exact
cost facts separately from model prose. Changed rules hide earlier answers.

See [the contract and frontend handoff](../../../docs/supplier-recommendation-modes.md).
