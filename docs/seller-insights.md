# Seller opportunities and on-demand alerts

Implemented additive backend proposal; frontend acceptance and browser integration
are pending. This feature is read-only and does not need the local model to run
its deterministic report. AI explanations use the existing opt-in local model.
No new dependency, migration, notification service or automatic action is added.

## HTTP contract

POST `/api/v1/products/{product_id}/insights` requires a bearer session, current
verified seller access and product ownership. The JSON body accepts only:

```json
{"period_days":30,"analysis_id":null}
```

period_days is a strict integer from one through ninety, default thirty.
analysis_id optionally selects an owned saved production analysis; otherwise
the latest analysis is used. Foreign products/analysis IDs return generic 404.
401/403 apply to authentication/role failures. Validation returns redacted 422
errors. Responses, including private failures, use Cache-Control: no-store.
Money and fractional rates serialize as decimal strings; IDs are UUID strings.

The response contains insight_version seller-insights-v1, product_id,
selling_unit, currency USD, as_of_date, current_period, previous_period, pricing,
costs, receipts, production, materials, alerts and notices. Window end_date is
exclusive. Both windows contain the same number of complete UTC dates, ending
at today's start; today's incomplete activity is excluded from trends.
The current approved price and selected analysis are assessed separately from
those historical windows, so an analysis saved today can still assess price.

## What the evidence establishes

- pricing assesses the current visible, seller-approved listing price using the
  shared production calculator, selected analysis costs, fee assumptions and
  seller margin targets. It includes source IDs, analysis_saved_on,
  listing_revision, price, unit_cost, break_even_price, target_price_minimum /
  target_price_maximum, profit_per_unit, margin and threshold booleans. Missing
  analysis, missing listing or incompatible product type/selling unit produces
  a distinct status with unavailable amounts null. An old analysis is an old
  modeled basis; it does not establish current actual costs or profits.
- costs compares the latest saved unit-cost snapshot in each closed period.
  IDs and previous_saved_on/current_saved_on identify the sources. The latest
  incompatible snapshot is not silently skipped. Missing periods or changed
  type/unit/version remain missing_period_evidence or incompatible_basis.
  Save-time differences do not prove expense inflation or causation.
- receipts contains previous/current seller-wide approved receipt aggregates:
  dates, receipt_count, recorded_total, category_totals and limitations. Both
  receipt and expense ownership are checked; purchase dates are seller-confirmed.
  A difference is available only if both periods contain approved records.
  Missing records do not prove zero actual spending. These totals are **not
  deducted from modeled profit again**, assigned to this product, or treated as
  a complete accounting ledger. See [receipt scope](assistant-receipt-expenses.md).
- production includes effective, uncorrected product reports completed in the
  current period, with matching product type and selling unit. It reports
  included_records, excluded_basis_records, total_units, sellable_units,
  non_sellable_units and sellable_fraction (null without positive total output).
  Superseded records stay excluded even if their correction falls outside the
  period. Non-sellable output is not automatically avoidable waste.
- materials groups current-period waste ledger quantities by material ID and
  recorded canonical unit, never across materials/units. Each row has material_id,
  current label, unit, exact quantity and movement_count. No cost valuation,
  consumption forecast or selected-product allocation is inferred.

Differences use exact Decimal arithmetic, six-place half-up display rounding,
change = current minus previous and relative_change = change / previous.
A zero baseline leaves relative_change null; rates are fractions, not percentages.
Source labels and seller reports remain unverified.

## Alert rules and limits

Each alert contains code, severity, scope, source, message and suggested_review.
No user-configured threshold is invented:

| Code | Trigger | Scope |
| --- | --- | --- |
| UNSUSTAINABLE_PRICE | Approved price below modeled fee-aware break-even | product |
| LOW_MARGIN | Otherwise below the seller's minimum modeled margin target | product |
| SAVED_UNIT_COST_INCREASE | Positive compatible saved unit-cost difference | product |
| REVIEWED_EXPENSE_TOTAL_INCREASE | Positive receipt-total difference with both periods recorded | seller |
| NON_SELLABLE_OUTPUT | Positive effective non-sellable output | product |
| RECORDED_MATERIAL_WASTE | Recorded material waste groups present | seller |

Suggested reviews are conditional opportunities, not proven causes or promised
savings. Mandatory quality, safety and ethical requirements remain binding.
The report never edits price, stock, recipes, Quality Locks or payment records.
An empty alert list does not certify business health or complete evidence.

Bounds: twenty-five saved cost snapshots across both periods, one hundred
effective production reports, two hundred material waste movements and twenty
material/unit groups. Exceeding a bound returns 409 INSIGHT_SCOPE_TOO_LARGE,
never partial alerts. Each receipt period permits two hundred approved records;
the existing 409 ASSISTANT_EXPENSE_REPORT_TOO_LARGE and
UNSUPPORTED_EXPENSE_EVIDENCE guards apply. Unsupported selected analysis versions
return 409 UNSUPPORTED_EVIDENCE_VERSION. A report re-read that changes returns
409 INSIGHT_EVIDENCE_CHANGED; retry against current evidence.

## Assistant and saved dialogue integration

POST /api/v1/assistants/seller accepts optional insights with period_days;
the existing analysis_id also selects its pricing basis. Example with a
synthetic illustrative owned product ID:

```json
{
  "product_id":"59a9818e-37a5-47c0-9302-b1b54ab67514",
  "question":"What recorded opportunities should I review while preserving quality?",
  "insights":{"period_days":30}
}
```

Saved seller scopes accept the same insights option. Every turn recomputes the
rolling windows and current evidence, including after a backend restart. Prior
answers whose evidence changed are withheld under the existing conversation
rules; old prose does not become new evidence. Follow-ups retain the selected
scope. Stateless questions remain stateless. Explicit scope selection is
required; questions alone do not automatically opt into this report.

Evidence title: Private seller opportunities and on-demand alerts. Find it by
title and current response-local evidence key, never a fixed array position.
Model context gets qualitative statuses, coverage, alerts and policy only.
The backend renders exact financial/quantity facts separately. Raw receipt OCR,
merchant names, receipt items, production notes and material movement reasons
are not selected or forwarded. Buyers cannot request this private extension.
Authentication and evidence are rechecked after inference and before saving;
changes return existing assistant/conversation conflicts rather than stale copy.

## Follow-up

The recommended current design provides on-demand reviews using existing
seller targets and recorded evidence. More detailed configurable thresholds,
category-specific baselines, persistent alert acknowledgement/deduplication,
notification delivery, actual-cost reconciliation, waste reasons and confirmed
product/material links are later improvements. No scheduling or delivery
infrastructure is implied. See DOMAIN-010 in the
[decision register](local-mvp-decisions.md).
