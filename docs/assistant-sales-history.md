# Seller assistant sales and cost-history questions

This additive assistant feature depends on local assistant PR #38. Its own PR
targets main and stays draft until prerequisites are integrated and refreshed.
Frontend integration is a separate responsibility.

POST /api/v1/assistants/seller retains its existing fields and adds optional
history_period: {start_date, end_date}. Dates are UTC calendar dates; end_date is
exclusive and must be 1-366 days after start_date. Extra fields remain forbidden.
The period selects seller-wide sandbox capture-cohort totals and the selected
owned product's saved production-analysis history. Returned facts label these
different scopes explicitly.

Without an explicit period, English sales/revenue/refund/history/trend questions
activate bounded history. Supported phrases include last month, this month,
last year, yesterday, today, last week and last N days. Last week means the most
recent seven UTC dates, including today. Generic history questions default to
the most recent thirty dates. Unsupported calendar-year/quarter or forecast
questions require an explicit period rather than silently guessing. A supplied
period overrides phrase parsing. Period dates and selected sources appear in evidence.

## Accuracy and limits

Sales reuse the existing owner-scoped sales repository and deterministic summary
service. Only verified completed sandbox captures are included. Completed
refunds are counted as of reporting, not as a cash-flow statement for the period.
Frozen historical order costs are preserved; latest product costs are never
backfilled into prior orders. Unknown fees/costs and unresolved refunds preserve
unknown profit. No buyer identity, provider payload, private payment reference or
order-level customer information is sent to the model.

Cost history includes at most twenty-five saved analyses within the selected
period; overflow returns 409 ASSISTANT_HISTORY_TOO_LARGE. The existing one-thousand
captured-sale limit returns 409 REPORT_TOO_LARGE. Narrow the period instead of
accepting silently truncated aggregates. Normal assistant evidence-budget limits
also apply.

The history uses analysis save times, not actual procurement/expense dates.
Latest-minus-earliest costs are calculated only when at least two selected
snapshots share their product type and selling-unit label. Component costs are
normalized by each snapshot's own yield before comparison. Matching labels do
not verify equal contents, recipe, allocations or quality; differences do not
prove inflation, expense causation or seasonality.

Exact dates, amounts and outcomes remain in server-rendered facts and typed
evidence. AI receives qualitative coverage/driver information and limitations.
Access, selected evidence and aggregates are rechecked after inference.
Generation timestamps are not treated as changing source evidence.

This remains read-only: no stock, payments, costs, prices, disclosures or analysis
history are changed. Questions outside the evidence scope cannot establish
actual procurement spending, live earnings, payouts or forecasts.

## Synthetic request

~~~json
{
  "question": "Explain my sales and cost history for this period.",
  "product_id": "11111111-1111-4111-8111-111111111111",
  "history_period": {
    "start_date": "2026-01-01",
    "end_date": "2026-02-01"
  }
}
~~~

Use actual owned synthetic IDs and the existing bearer header. The response adds
evidence titled Private seller-wide sandbox sales history and Selected product
saved cost history; evidence keys remain response-local. The original assistant
contract, cache/error protections, read-only behavior and disabled-by-default
local provider still apply. See [the foundation](local-assistants.md).

Conversational memory is separate: history-aware questions do not themselves
retain prior turns. Temporary versus durable conversation retention is awaiting
the user's decision. No broader backlog or continuous cycle is enabled here.
