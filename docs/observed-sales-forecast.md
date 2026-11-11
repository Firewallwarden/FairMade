# Observed sales-rate baseline and inventory planning

Implemented backend proposal; frontend acceptance and browser integration are
pending. The confirmed choice is option 1: use backend-verified FairMade sales
only. Seller-entered/imported offline sales history (option 2) is recorded as
a possible later enhancement, not accepted as input or silently mixed with
verified captures. See DOMAIN-007 in [the decision log](local-mvp-decisions.md).

## Scope and source

POST /api/v1/products/{product_id}/forecasts requires a valid bearer token,
verified seller role and ownership of the selected product. A foreign or
missing product returns 404; a buyer without seller access receives 403.
Responses and errors use Cache-Control: no-store. The deterministic endpoint
works without an enabled AI provider.

The optional local Qwen assistant explains this calculation through existing
seller questions and saved seller conversations. It does not choose quantities,
invent missing sales, or change stock, production, supplier choices, Quality
Locks, prices, orders or payments. No new migration, model, paid service or
infrastructure is introduced.

Illustrative standalone request with an actual owned product UUID in the path:

~~~json
{
  "lookback_days": 28,
  "horizon_days": 7
}
~~~

Both fields are strict JSON integers. Lookback is 14..90 days, default 28;
horizon is 1..30 days, default 7. An empty object uses these defaults.
Client forecasts, arbitrary as-of dates, prices, offline records, confidence
scores, dates and source data are rejected as extra fields. Use real sales
through the existing sandbox order/capture workflow; illustrative examples
and test fixtures are not actual merchant demand.

Only lines for the owned product in seller-owned orders with a completed
backend-verified sandbox checkout, non-null capture ID and a verification
date inside the selected closed-day window are queried. Pending/unverified
payments and other products/sellers are excluded. Historical selling units and
product type come from the immutable approved public order snapshot, never
from today's product metadata. Missing, ambiguous or incompatible historical
bases are excluded and counted; they are not relabeled or converted.

Any order with a refund request is conservatively excluded, including a
denied request. This is an explicit implementation policy rather than a user
choice about net demand; cancellation/refund timing, partial returns and
restocking are not reconstructed. Capture verification time, not order time
or assumed pickup/delivery, determines the sales date. Captures before their
order or orders before the product's creation date are excluded as inconsistent.
No buyer identities, provider payloads, capture references or order IDs enter
the forecast response or model evidence.

A complete query has at most 1,000 captured product lines, including lines
later excluded by refund/basis checks. Overflow returns 409
FORECAST_SCOPE_TOO_LARGE; narrow the lookback rather than silently sampling.
The repository uses the existing seller/order/product and verified-capture
indexes. It reads only dates, quantity, an approved public order snapshot
and refund-request presence, then reduces them to minimal observations.

## Closed dates, rate and stock formulas

Let today be the current server UTC date. The observation window ends at
today, exclusive: partial sales today and future captures are not used.
The start is the later of today minus lookback_days and the day after product
creation. The creation date itself is partial and is excluded. Future or
inconsistent product creation dates produce zero complete dates and
insufficient history, never a reversed interval.

The window contains every complete calendar date, including dates without
qualifying sales. Missing sales contribute zero observed captures; this does
not prove zero customer demand. Historical publication exposure, holidays,
stockouts, offline sales, promotions and lost sales are unknown.

A baseline requires at least fourteen complete dates and qualifying sales on
at least three distinct dates. These are transparent implementation thresholds,
not statistical validation or a confidence interval. Large sales on one day
do not bypass the minimum-date threshold. Insufficient history returns null
rates/projections/planning quantities rather than zero or fabricated estimates.

With sufficient history:

- daily_rate = included selling units / complete calendar dates.
- projected_units = included units × horizon_days / complete dates.
- projected_remaining_units = current available units minus projected units.
- additional_whole_units = max(0, ceiling(exact projected units) − available units).
- days_of_cover = available units × complete dates / included units.

Rate/projection/coverage displays are decimal JSON strings rounded half up to
six places in an explicit high-precision decimal context. Whole-unit ceiling
uses exact integer arithmetic and is never derived from a rounded display.
An additional-unit number is a conditional planning quantity, not a production
instruction or order. No monetary forecast is calculated.

Current available stock reuses the established stock service, including live
unpaid/uncertain-checkout holds. A missing inventory revision, different current
selling unit or negative/inconsistent availability returns inventory status
unknown and null coverage/shortfall fields. It never becomes an assumed empty
warehouse. Sufficient sales history can still yield a baseline when inventory
is unknown; stock projections remain null.

This is a constant observed-sales-rate baseline, not a calibrated demand model,
seasonal forecast, demand guarantee or raw-material/ingredient replenishment
model. Product/unit label equality does not establish identical package size,
grade, animal output or historical variants. Review those limitations before
using the numbers for operational decisions.

## Response and errors

ForecastResponse is available in generated OpenAPI and contains:

- forecast_version: observed-sales-rate-v1; environment: sandbox;
  basis: backend_verified_fairmade_captures.
- product_id, product_type, selling_unit, as_of_date and the effective request.
- status: baseline_available or insufficient_history.
- history: inclusive start_date, exclusive end_date, complete_days, sale_dates,
  included_lines, units, excluded_refund_lines, excluded_basis_lines,
  excluded_timing_lines and the bounded daily units series.
- daily_rate and projected_units, nullable decimal strings.
- inventory: status known/unknown, available_units, projected_remaining_units,
  additional_whole_units and days_of_cover, with appropriate nulls.
- warnings and mandatory notices.

Warnings distinguish insufficient complete dates/sale dates, excluded refund,
historical-basis or inconsistent-time lines, and unknown inventory. A baseline
can include exclusion warnings; it is never presented as full demand coverage.
Stock and source aggregates are reread before return. Changed evidence returns
409 FORECAST_CHANGED; changed access returns its normal authorization/not-found
error. Later stock or captures can change the result; this creates no reservation.

## Seller assistant and saved continuity

Existing POST /api/v1/assistants/seller adds optional forecast with the same
request shape. Existing callers without that field retain their behavior.
SellerScope in POST /api/v1/assistants/conversations supports the same additive
field. All existing owner, role, revision, retry, deletion and retention controls
remain in force.

Illustrative seller question:

~~~json
{
  "question": "Explain my observed sales baseline and stock planning limitations.",
  "product_id": "11111111-1111-4111-8111-111111111111",
  "forecast": {
    "lookback_days": 28,
    "horizon_days": 7
  }
}
~~~

Illustrative saved conversation:

~~~json
{
  "request_id": "90000000-0000-4000-8000-000000000001",
  "scope": {
    "role": "seller",
    "product_id": "11111111-1111-4111-8111-111111111111",
    "forecast": {
      "lookback_days": 28,
      "horizon_days": 7
    }
  }
}
~~~

Replace illustrative UUIDs. Turns use the existing request_id,
expected_revision and question shape. Scope fixes lookback and horizon;
free-text follow-ups cannot silently replace them. A changed window needs a
reviewed new scope. Each turn rolls the window forward with the server UTC date
and rereads current sales, historical compatibility and stock.

An explicit forecast selects its own closed-date observation window, so it
suppresses implicit natural-language history-period inference. Supply a separate
history_period explicitly if an answer should also include the existing
seller-wide financial history. Those financial aggregates have a different
scope and refund treatment from this product-unit baseline; do not equate them.

Evidence is titled Private product observed sales baseline and inventory
projection. Exact units, dates, rates and planning outcomes appear in
response.facts generated by the server. The model receives qualitative
availability, warnings and assumptions, not raw orders, customer data, daily
series, exact projections or financial payloads. It may explain limitations;
it cannot fill a sparse sample with invented figures or take an action.

The existing assistant source/access checks run before and after inference
and again before a turn is saved. Changed stock/sales/unit/window evidence
invalidates historical answers and suppresses stale model prose replay.
Saved questions retain bounded dialogue across restarts with the established
thirty-day inactivity retention. See [saved conversations](assistant-conversations.md).
An answer is not proof of universal model correctness or browser continuity.

## Frontend and later enhancements

The frontend developer owns window controls, explicit units, history coverage,
null/insufficient states, warning/notices display and safe facts/citation
rendering in saved conversations. Do not label an observed sandbox rate as
verified future demand. No browser integration or video recording was performed
by this backend change.

Option 2 is a potential later implementation: explicit seller-entered/imported
offline history, with source labels, validation, deduplication, correction and
retention policy before it influences forecasts. Other optional improvements
include publication/stockout exposure, returns/partial refunds, unit/variant
history, lead times, seasonal models, backtesting/calibration and raw-material
mapping. These need evidence and separate design; the follow-up does not
authorize ingestion, an external provider, spending or infrastructure.

## Validation

The affected regression suite passed 233 tests across forecasting, assistants,
sales and orders, with 13 opt-in checks skipped and one existing framework
deprecation warning. A real local Qwen saved forecast explanation and reference
follow-up passed separately. Ruff lint/format passed for 343 Python files,
148 local documentation links resolved, all three request examples validated
against their actual schemas, and three affected OpenAPI operations required
authentication. These are backend checks, not a full-backend-suite rerun,
calibrated forecast validation, actual merchant demand or a browser demo.
