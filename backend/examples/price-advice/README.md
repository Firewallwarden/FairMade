# Synthetic conditional pricing examples

Use an owned saved pricing review and its product ID in place of the illustrative
UUIDs. The review pins its cost analysis and selected observations/evaluations.
Use an explicit production-unit mapping for numerical market context; otherwise
the result is economics-only. Matching claims are not certification.

POST request.json to /api/v1/products/{product_id}/pricing-recommendations with
a current seller session. The deterministic endpoint works without AI. Display
source units/dates, quality gates, mapping and conditions with the review range;
never substitute zero for a missing recommendation or choose the highest quote.

With the existing local assistant enabled, POST conversation.json to
/api/v1/assistants/conversations. Ask why the range is conditional, then why it
does not establish objective fairness. Render exact facts separately from model
prose. These requests create no price change or public publication.

See [the contract and frontend handoff](../../../docs/conditional-pricing-recommendations.md).
