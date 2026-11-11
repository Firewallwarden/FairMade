# Supplier recommendations for seller review

Implemented additive backend proposal; frontend acceptance and integration are
pending. The deterministic selector works without AI. Saved seller assistants
can explain its current evidence with the existing opt-in local Qwen model.
No new migration, provider, infrastructure or automatic business action is added.

[Implementation #52](https://github.com/Firewallwarden/FairMade/pull/52) is a
main-targeted draft dependent on #38 through #42. Refresh and revalidate against
verified main after prerequisite integration before review readiness.

## Endpoint and options

POST /api/v1/products/{product_id}/supplier-recommendations requires a bearer
session, current verified seller access and ownership of the selected product.
The report must belong to that same product through its sourcing input.
Example with a synthetic illustrative saved-report ID:

```json
{
  "supplier_report_id":"9f6f34cc-6e55-4275-92b3-75812f949f03",
  "mode":"balanced",
  "cost_objective":"purchase_outlay",
  "preferences":[
    {"key":"preferred_grade","label":"Preferred grade claim","type":"choice","allowed_values":["premium"]}
  ]
}
```

mode is savings, quality or balanced (default). cost_objective is purchase_outlay
(default) or usable_unit. preferences contains zero through eight distinct
attribute-key rules using the existing boolean/choice/numeric rule types and
validation. It is an **optional preference list**, not a replacement Quality Lock
set. Numeric values remain bounded decimal strings; numeric units must match
exactly, with no automatic conversion. Request order defines preference priority
in quality mode. Unknown fields, duplicate keys, invalid types/limits/modes and
missing/invalid report IDs return redacted 422 errors.

The response contains recommendation_version supplier-review-modes-v1, basis
seller_reported_unverified, product_id, supplier_report_id, sourcing_input_id,
input_label, rule_revision, as_of_date, required_quantity, options, rows,
selected_quote_ids, product_impact and notices. IDs are UUID strings, dates are
UTC calendar dates, and money/fractional values are decimal strings. All private
success/failure responses use Cache-Control: no-store. No record is saved by this
endpoint; the original comparison history remains immutable.

## Mandatory eligibility first

The selector reuses a shared supplier-domain reader that recalculates the saved
report's quote snapshots against **current** sourcing-input rules and today's
date. It does not trust the old report's eligibility or substitute newly entered
quotes. The existing hundred-quote bound and comparison version checks apply.
Current rule revision and as-of date are explicit in the result.

Mandatory failed/unknown/not-evaluated claims, future/stale/expired observations,
unavailable/unknown supply, missing transport cost, incompatible quantity units,
unsupported purchase counts and insufficient available packages exclude a quote
before every recommendation mode. An excluded quote is never selected even if
cheaper or matching every optional preference. Missing mandatory evidence stays
unknown. Existing warnings and every exclusion remain visible.

This is selection **for sourcing-input review**. Finished-product effects are
not assessed; product Quality Locks remain binding and require their own review.
product_impact is always not_assessed_no_substitution_authorized. No replacement
recipe, supplier purchase, price, inventory or Quality Lock change is authorized
by a selection. It is not proof that a substitution would preserve all finished
product properties. Supplied claims are unverified, never certifications.

## Exact selection behavior

The shared comparison calculator handles usable yield, whole packages, minimum
bulk purchases and transport charged once. purchase_outlay compares total USD
outlay for satisfying the required quantity. usable_unit compares the existing
six-decimal rounded cost per usable reference unit, including surplus purchased.
They can produce different selections; the latter does not imply the smallest
cash outlay. All exact objective ties are preserved. No float, LLM arithmetic,
invented benchmark saving or conversion is introduced.

Each optional preference produces a normal typed check and a known-match flag.
Only a passed supplied claim matches. Failed and unknown optional claims do not
match, but their distinct check statuses/reasons are retained. An unknown match
does not mean zero actual quality, and a failed optional preference does not by
itself make a mandatory-eligible quote ineligible.

- savings selects every eligible quote tied at the minimum chosen objective cost.
- quality first chooses the lexicographically highest ordered known-match vector
  (the first preference has highest priority), then minimum cost with all ties.
  This is seller-preference matching, not an overall quality grade or score.
- balanced returns all non-dominated eligible tradeoffs: a quote is removed only
  if another costs no more, matches every preference at least as well, and is
  strictly better on cost or a match. There is no invented weighting. Identical
  cost/match ties all remain; incomparable preference/cost options all remain.

With no preferences, every mode reduces to minimum-cost ties and reports that
limitation. If no eligible quote has any known optional match, the response
explicitly says selection reflects cost among unmatched claims. If no quote is
eligible, selected_quote_ids is empty; no substitute or saving is inferred.

Each response row includes quote_id, supplier_name, observed_on, source,
mandatory_checks, preference_checks, eligible, exclusion_reasons, cost,
objective_cost, preference_matches, selected_for_input_review and selection_reason.
Excluded costs/objective_cost are null, preventing excluded options from being
presented as savings. selection_reason is excluded, selected or not_selected.
selected_quote_ids is stably sorted by UUID; rows retain saved report order.
Source attribution is retained, but raw quote notes and private provider records
are not returned. There is no public or buyer endpoint for this private report.

## Assistant and conversational continuity

Seller questions and saved seller scopes accept optional recommendations with
mode, cost_objective and preferences, alongside the existing supplier_report_id
and owned product_id. recommendations requires supplier_report_id. Existing
requests remain unchanged. The selected mode/preferences are fixed conversation
scope; they are not inferred from prose or silently remembered as new settings.

```json
{
  "product_id":"59a9818e-37a5-47c0-9302-b1b54ab67514",
  "supplier_report_id":"9f6f34cc-6e55-4275-92b3-75812f949f03",
  "recommendations":{"mode":"balanced","cost_objective":"purchase_outlay","preferences":[]},
  "question":"Explain the input-review tradeoffs without approving a substitution."
}
```

Evidence title: Current supplier recommendation mode and optional preference
tradeoffs. Find by title and current response-local citation keys. Exact costs
render separately as server-calculated facts. Qualitative context contains mode,
objective name, ordered rules, mandatory/optional checks, exclusions, selected
status and policy. It omits exact costs, raw quote notes and provider data.
Existing owner-only supplier explanations continue to show exclusion reasons.

Saved follow-ups survive restarts and recompute current requirements, quote
freshness and selection every turn. Previous answers are withheld when evidence
changes. Access/evidence is checked after inference and before turn persistence;
changed rules or revoked sessions cannot save a stale recommendation. Stateless
questions remain stateless. Buyers cannot request the private extension.

## Errors and future depth

401/403 apply to session/seller access; foreign product/report IDs use generic
404. Unsupported saved versions return 409 UNSUPPORTED_EVIDENCE_VERSION.
Report re-read changes return 409 SUPPLIER_RECOMMENDATION_CHANGED. Existing
assistant inference, source-change, response-size and conversation guards apply.

Recommended current behavior uses explicit supplied claims and transparent
preference/cost tradeoffs. Optional later depth includes seller-reviewed weighted
preferences, quality evidence confidence/verification, explicitly chosen private
reliability signals, confirmed recipe/substitution effects, sourcing-input links,
actual savings baselines and a proposal/review workflow for applying changes.
There is no automatic production requirement to adopt these alternatives.
See DOMAIN-012 in [the decision register](local-mvp-decisions.md).
