# Conditional sustainable price recommendations

Implemented additive backend proposal; frontend acceptance and browser integration
are pending. The deterministic Fair Price Engine combines explicit production
economics, selected reported market context and mandatory quality evidence into
a **conditional range for seller review**. The existing local assistant explains
its limitations. It never chooses the highest price, changes a listing, relaxes
quality or declares an objectively fair price.

[Implementation #54](https://github.com/Firewallwarden/FairMade/pull/54) is a
main-targeted draft dependent on #38 through #42. Refresh and revalidate against
verified main after prerequisite integration before review readiness.

## Endpoint and sources

POST /api/v1/products/{product_id}/pricing-recommendations requires a current
bearer session, verified seller access and product ownership. Body with a
synthetic illustrative owned saved-review ID:

```json
{"review_id":"14ca24f3-ed3b-4aaa-bf5a-70bd0f20f2c8"}
```

The saved review must belong to that product. Its request pins the production
analysis, selected comparison report/observations, selected quality evaluations
and optional production-unit mapping. The shared review-domain reader reloads
those owned immutable sources, current product metadata/current Quality Locks,
and reassesses quote freshness as of the current UTC date. It does not silently
switch to a newer analysis or newly entered observations. Original reviews,
comparisons and evaluations remain unchanged. No new migration/provider or
infrastructure is added, and this report endpoint does not require AI enabled.

The response contains advice_version conditional-price-range-v1, basis
seller_reported_unverified, product_id, review_id, pricing_analysis_id,
analysis_saved_on, as_of_date, analysis_selling_unit, current_selling_unit,
status, quality_status, current_rule_revision, market_status, currency USD,
unit_cost, break_even_price, seller_target_range, selected_market_range,
recommended_review_range, production_unit_quantity, market_reference_quantity,
selected_quality_evaluation_ids, market_sources, reasons and notices. IDs are
UUID strings; dates are UTC calendar dates; amounts are decimal strings. A range
contains minimum/maximum, never a chosen point price.

analysis_saved_on describes record save time, not when actual costs were measured.
Cost assumptions, labor compensation, overhead, fees and margins remain the
seller's modeled unverified basis. Existing calculator warnings, including
missing labor/overhead, are retained. No missing cost, risk allowance, demand or
profit is invented or independently verified.

## Eligibility and exact range policy

1. A current product-type or selling-unit mismatch with the saved analysis blocks
   the recommendation as basis_changed. Diagnostic amounts retain the historical
   analysis_selling_unit; they are not relabelled as current per-product costs.
2. When mandatory product rules exist, selected quality claims must all pass and
   apply to the current rule revision/rule snapshot. Failed, unknown, missing,
   unevaluated or outdated selected evidence produces quality_blocked with no
   recommended range. Matching claims remain unverified. No configured rules
   produces quality_status not_configured, explicitly **not** quality assurance.
3. Missing comparison evidence, mismatched product types, missing explicit unit
   mapping, or no fresh convertible observations yields economics_only guidance
   from the seller's target range, labelled without usable market support.
4. Otherwise, the policy intersects the seller-target range with the selected
   descriptive price range on the seller-declared production-unit mapping.
   The lower bound rounds **up** to cents; the upper bound rounds **down** to
   cents. Prices remain positive and within the existing Passport publication
   limit of USD one billion. Thus a recommended cent price stays inside both
   applicable ranges and supported publication bounds.
5. An overlapping supported cent range yields conditional_overlap. If market
   observations lie below the target range, status is target_market_gap and
   there is no recommendation; a below-break-even reference adds a separate
   warning. A market range above the seller target yields market_premium_gap,
   again without choosing a higher price. A fractional-cent gap, zero-only model
   or out-of-supported-bounds model yields no_cent_price with no recommendation.

No range gap silently lowers compensation, quality or margin targets. No market
premium automatically raises a price. All range math reuses the existing exact
Decimal calculations and displayed six-place comparison values; no floats or
LLM arithmetic participate. A non-null range is a conditional proposal for
review, not proof of profitability, affordability, demand or universal fairness.

quality_status is not_configured, selected_claims_match_unverified or blocked.
market_status retains the established pricing-review statuses. The report
preserves original evidence warnings and current selection limitations.

## Market quantity and provenance boundaries

production_unit_quantity is the review's explicit optional seller declaration
for one saved production selling unit. market_reference_quantity is the actual
quantity used in the reassessed comparison. Every market_sources.normalized_price
uses that reference quantity. If a production mapping is missing, these prices
must **not** be displayed as prices per sold product. selected_market_range is
null until the mapping and other comparability conditions permit its use.

Each bounded market source exposes observation_id, label, location, observed_on,
source name/kind/reference, included, normalized_price and exclusions. Raw quality
notes and price notes are omitted. Existing hundred-observation and hundred-
evaluation selection bounds apply. Source attribution/dates remain available,
but locality, representative market coverage, equivalent ingredients/quality,
taxes, shipping and discounts are not independently verified or reconciled.
The overlap is conditional on that uncertainty; it is not a claim that all
products are equal or that the observed maximum is an appropriate price.

## Assistant and saved conversations

Seller questions and saved seller scopes accept optional pricing_review_id in
addition to the existing owned product_id. Example:

```json
{
  "product_id":"59a9818e-37a5-47c0-9302-b1b54ab67514",
  "pricing_review_id":"14ca24f3-ed3b-4aaa-bf5a-70bd0f20f2c8",
  "question":"Explain the conditional price range and its evidence limits."
}
```

Selecting a review pins the base economics and requested price scenarios to
that review's analysis. An explicitly supplied conflicting analysis_id returns
409 PRICING_SOURCE_MISMATCH. Omitting the new option retains existing behavior.
Saved follow-ups keep review scope across restarts, recompute current quality
and quote freshness, and withhold stale answers after evidence changes. Existing
post-inference access/evidence checks and atomic turn persistence apply.

Evidence title: Current conditional sustainable price recommendation. Use current
response-local evidence keys. Exact costs, ranges and dates render as server
facts. Model context contains statuses, availability, reasons and limitations,
without exact ranges or raw observation notes. It must explain a missing or
blocked recommendation rather than invent one. Buyers cannot request this
private review option; public pricing explanations still respect seller disclosure.
No advice is automatically published, charged or written into another record.

## Errors and handoff

401/403 cover session/seller failures; foreign product/review/evidence IDs return
generic 404. Invalid/unknown body fields return redacted 422. Unsupported saved
versions return 409 UNSUPPORTED_EVIDENCE_VERSION. A changed direct report re-read
returns 409 PRICE_ADVICE_CHANGED. Existing assistant/conversation source, size,
inference and retry guards apply. All private responses/errors use no-store.

Frontend integration should show the status, source analysis date/unit, quality
gate, explicit mapping, conditions and separate source ranges alongside the
review proposal. Do not replace null with zero, relabel an old unit, infer
ingredient equivalence, or turn an economics-only result into market validation.
Publication and final pricing remain deliberate seller actions.

Later optional depth includes verified/quality-matched local comparables,
representative sample/confidence policies, richer cost freshness/completeness,
actual-cost reconciliation, evidence-backed demand/seasonality and reviewed
price application. The recommended current policy uses selected manual evidence
without pretending it establishes those deeper findings. See DOMAIN-014 in
[the decision register](local-mvp-decisions.md).
