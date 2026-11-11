# Saved cost calendar and descriptive annual comparisons

Implemented additive backend proposal; frontend acceptance and browser integration
are pending. This is a read-only view of saved production-cost models. It does
not establish actual expense timing, inflation, causes or validated seasonality.
No new migration, provider or infrastructure is introduced.

[Implementation #55](https://github.com/Firewallwarden/FairMade/pull/55) is a
main-targeted draft dependent on #38 through #44 and #50. Refresh and revalidate
against verified main after prerequisite integration before review readiness.

## Endpoint and calendar scope

POST /api/v1/products/{product_id}/cost-calendar requires a bearer session,
current verified seller access and product ownership. Body:

```json
{"months":24}
```

months is a strict integer one through thirty-six, default twenty-four. The
report uses that many **complete UTC save months**, ending at the first day of
the current month, exclusive. The current incomplete month is excluded. For an
illustrative as-of date in November, a twenty-four-month report includes November
two years earlier through October of the current year. No partial-month estimate,
future projection or hidden extension outside the requested window is added.

The response contains calendar_version saved-cost-calendar-v1, basis
seller_recorded_save_month_not_actual_expenses, product_id, product_created_on,
as_of_date, start_date/end_date, currency USD, selling_unit, requested_months,
recorded_months, total_snapshots, calendar_evidence_status, seasonality_status,
months, year_over_year, calendar_month_summaries and notices. Dates are ISO UTC
calendar dates; month keys are YYYY-MM; money/rates are decimal strings; IDs are
UUID strings. All private responses/errors use Cache-Control: no-store.

The complete matching source set is bounded at one thousand saved analyses;
larger scopes return 409 COST_CALENDAR_TOO_LARGE rather than a truncated history.
Narrow the requested period or use a separately scoped deeper reporting design.
The query selects IDs, save dates, type/unit, versions, currency and unit_cost
only. Raw ingredient/cost labels, quantities, labor, instructions and notes are
not selected or forwarded by this feature.

## Monthly model snapshots

Each months entry contains month, status, record_count, compatible_record_count,
latest_analysis_id, latest_saved_on and unit_cost. The latest saved analysis in
that month wins, ordered by full save timestamp then UUID. It must use the
supported production-economics calculation/result version, USD, a usable bounded
unit-cost value and the current product type/selling unit. unit_cost is the
existing modeled production cost per selling unit; transaction fees, revenue,
actual cash spending and margin are different measures.

status is recorded, missing, basis_changed or unsupported_snapshot. Missing data
has no analysis ID/date/cost. A latest incompatible/unsupported snapshot retains
its source ID/date and a null cost; the report does not quietly select an older
convenient value. compatible_record_count makes the unused older coverage clear.
Recorded zero is a known zero in that saved model, distinct from a missing
amount and from a claim about actual zero production expense.

The value is neither a production-weighted monthly average nor a measured
month-end actual cost. Save dates may differ from cost occurrence dates; recipe,
yield, compensation, allocations and model assumptions may have changed. Same
type/unit labels do not establish equivalent ingredients or product quality.
Missing months, including periods before product creation, do not establish
zero actual cost. This foundation does not backdate records or invent history
for a newly created product.

## Annual and calendar-month comparisons

year_over_year compares each month with the same calendar month twelve positions
earlier **within the requested window**. At least thirteen requested months are
needed for any comparison slot. Each entry contains previous_month/current_month,
previous_analysis_id/current_analysis_id, status and difference. Both monthly
snapshots must be recorded on the current compatible basis; otherwise status is
missing_or_incompatible and both change fields are null.

For comparable snapshots, change is current minus previous and relative_change
is change divided by previous, rounded half-up to six places using exact Decimal
arithmetic. Rates are fractions, not percentages. A zero previous cost leaves
relative_change null while preserving the known absolute change. The same
nullable arithmetic is shared with seller period insight reports; their public
AmountChange shape and behavior remain unchanged.

calendar_month_summaries has twelve entries, one for each calendar month. Each
contains calendar_month (one through twelve), observed_years and
minimum_unit_cost/maximum_unit_cost across recorded latest monthly snapshots.
Unknown ranges remain null and missing years are not filled with zero. This is
descriptive grouping of supplied models, not a representative sample, quality
adjustment or independent evidence of a recurring seasonal mechanism.

calendar_evidence_status is descriptive_comparisons_available when at least one
year-over-year comparison is possible, otherwise insufficient_history.
seasonality_status is always not_established. Even a full window of models
does not independently verify seasonal effects, inflation, future demand or
future prices. No forecasting or price recommendation is changed by this report.

## Seller assistant and saved memory

Seller questions and saved seller scopes accept optional cost_calendar with the
same months option. Example with a synthetic illustrative owned product ID:

```json
{
  "product_id":"59a9818e-37a5-47c0-9302-b1b54ab67514",
  "cost_calendar":{"months":24},
  "question":"Explain the saved calendar differences and why they do not prove seasonality."
}
```

This source is explicit; question prose alone does not opt into it. Existing
history periods and on-demand insights remain separate sources with their own
limits. Evidence title: Private saved cost calendar and annual comparisons.
Use current response-local citation keys and titles, not array positions.

Exact monthly values, dates, annual changes and cross-year descriptive bounds
render as server facts. Model context receives qualitative coverage, supported
comparison flags/directions, calendar month names and limitations, without raw
cost labels or exact values. Direction is derived deterministically, not guessed
by the model. It must not transform a saved-model difference into an observed
expense increase, cause, seasonal pattern or guarantee.

Saved follow-ups retain the selected month count, survive backend restarts and
recompute the rolling closed-month window/current source evidence. Changed
history or current selling basis withholds stale answers. Authentication,
ownership and current evidence are checked after inference and before saving;
changes cannot persist stale output. Independent questions remain stateless.
Buyers cannot request or access this private source. Existing conversation/source
size and inference limits apply. No business record is mutated by an answer.

## Errors, examples and future depth

401/403 cover session/seller failures; foreign product IDs use generic 404.
Invalid types, bounds and extra fields return redacted 422. A changed direct
report re-read returns 409 COST_CALENDAR_CHANGED. Scope overflow returns the
bounded-history error above; unsupported monthly snapshots stay visibly unknown
rather than silently converting currencies or interpreting malformed evidence.

The supplied examples are request shapes, not real historical cost claims.
Synthetic backdated records used by automated tests live only in temporary
test databases. A fresh local product can correctly show insufficient history.
Frontend may use clearly labelled mock history when demonstrating a populated
calendar; that is not evidence to publish as the seller's actual history.

Later optional depth includes explicit cost-occurrence histories/imports,
actual-cost and volume reconciliation, quality/recipe/version comparability,
representative multiple-cycle data, validated seasonal/confidence models and
explicitly reviewed use in forecasting/pricing. This report is the recommended
descriptive foundation; deeper validated seasonality remains future work. See
DOMAIN-015 in [the decision register](local-mvp-decisions.md).
