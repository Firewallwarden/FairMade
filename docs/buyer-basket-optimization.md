# Single-storefront basket optimization

Backend implementation, additive frontend contract proposal. The user selected
option 1: one seller/storefront per basket. Option 2, shopping plans across
multiple sellers with separate orders and pickups, is explicitly a later
enhancement. It is not authorized as part of this implementation.

## Behavior and objective

The buyer supplies required quantities and acceptable alternatives for each
need. The server selects one eligible listing per need and minimizes their
complete merchandise subtotal. It never reduces quantities to meet a budget,
adds extras to spend remaining money, invents discounts, changes published
prices, or places an order. The minimum is among the supplied alternatives,
not a claim about every item in the storefront, the local market, quality,
nutrition, or overall value.

Needs have disjoint listing IDs; the current catalog has one listing per
product. Requested quantities are fixed and stock does not overlap between
needs. Therefore choosing the lowest eligible line cost for each need also
minimizes the complete subtotal. Affinity breaks equal-cost ties only, followed
by a stable listing UUID. The implementation is linear in the bounded input;
there is no model-generated arithmetic or unbounded combinatorial search.

All alternatives in a need must have the same product type, selling-unit label
and declared selling quantity (same quantity value and unit). This avoids
claiming savings by replacing a larger package with a smaller one. Different
grades, ingredients and quality are not equivalent merely because these fields
match. Missing declared contents or a mismatched basis in a multi-alternative
need returns BASKET_INCOMPATIBLE_ALTERNATIVES. A single fixed listing can use
its established selling-unit checkout basis without comparing contents.
Cross-unit normalization, package combinations and splits between alternatives
are follow-ups, not silent conversions.

## Endpoint and request

POST /api/v1/buyer/baskets/optimize requires the existing bearer token.
All responses, including validation/auth errors, use Cache-Control: no-store.
No seller role is required; a seller account retains buyer capabilities but
cannot plan a purchase from its own storefront. No Ollama connection is needed
for this deterministic endpoint.

Illustrative request; replace every UUID and revision with current approved
public data. This example assumes both alternative loaves declare the same
contents and belong to the given published storefront:

~~~json
{
  "storefront_id": "80000000-0000-4000-8000-000000000001",
  "budget": "40.00",
  "needs": [
    {
      "group_id": "bread",
      "quantity": 2,
      "alternatives": [
        {
          "listing_id": "70000000-0000-4000-8000-000000000001",
          "expected_listing_revision": 1
        },
        {
          "listing_id": "70000000-0000-4000-8000-000000000002",
          "expected_listing_revision": 1
        }
      ]
    }
  ]
}
~~~

Bounds are implementation limits rather than individually confirmed product
choices: 1..4 needs, 1..4 alternatives each, at most 16 distinct listing IDs,
strict integer quantities 1..10,000, unique group IDs matching ASCII letters,
digits, underscore or dash (1..32 characters). Each listing appears exactly
once across the request. An alternative has a UUID and positive strict
expected_listing_revision. Extra fields, including client prices, seller
account IDs, instructions, safety certification or custom evidence, are rejected.

The optional budget is a nonnegative USD decimal JSON string, at most
USD 1,000,000,000 and two decimal places, with text bounded to 64 characters.
Null or omission means no total basket limit. Zero is a real limit, not an
absent budget. The supported order subtotal ceiling remains USD 1,000,000,000.
All price multiplication and summation uses integer cents; no rounded
standard-unit display prices are used for checkout totals.

## Response and exclusions

BasketResponse is described in generated OpenAPI:

- optimization_version: single-storefront-basket-v1; storefront_id.
- status: ready, over_budget or unavailable.
- budget: USD currency/amount object or null.
- minimum_subtotal: minimum complete eligible merchandise subtotal, or null
  when a need cannot be met. For over_budget it is an explanation of the
  necessary merchandise amount, not a recommended unaffordable purchase.
- remaining_budget: nonnegative difference only for a ready budgeted plan.
- personalized and profile_revision: current owner's profile state.
- needs: group_id, fixed quantity, chosen_listing_id and candidate decisions
  with listing_id, eligible, exclusions and affinity_reasons.
- cart: the existing CartRequest shape, or null.
- preview: the existing CartPreview shape, or null.
- notices: mandatory scope, provenance, quality and no-purchase limitations.

Cart and preview, and every chosen_listing_id, are null unless the entire
basket is ready. An incomplete plan never presents a partial basket as meeting
the request. The server reuses the existing order preview service to validate
and price the ready cart. Explicit quantities and expected published revisions
are preserved for the existing order API; no idempotency key is needed for
planning because there are no order/stock/payment writes.

Only active publicly visible listings whose product belongs to the selected
currently published seller storefront are considered. Withdrawn, unpublished,
foreign-storefront and missing candidate IDs return the same 404 NOT_FOUND.
A stale supplied revision returns 409 LISTING_CHANGED; review and create a new
request using current public revisions rather than silently accepting a new price.
Own-storefront planning returns 409 SELF_PURCHASE.

Candidate exclusions include the existing profile rules ABOVE_BUDGET,
PRODUCT_TYPE_NOT_SELECTED, LOCATION_NOT_SELECTED and BUYER_EXCLUDED, plus
UNAVAILABLE and QUALITY_REQUIRES_ATTENTION. Inventory checks add
INVENTORY_NOT_CONFIGURED, INVENTORY_UNIT_MISMATCH or INSUFFICIENT_STOCK.
Unknown inventory is not purchasable. Existing live stock holds, including
uncertain checkout holds, follow the shared stock policy. Private stock ledgers,
costs and provider payloads are not returned. Exact public availability retains
the existing public catalog policy.

A disclosed needs_attention quality summary excludes a candidate. Missing
or matching unverified claims do not establish allergy/safety suitability,
certification, equal quality or acceptable substitution against an undisclosed
requirement. The buyer must review ingredients, disclosures and mandatory needs.
This feature does not add an unsupported safety-requirements language or relax
Quality Locks to produce a cheaper plan.

Sources are reread before return. A changed plan/profile/activity source causes
409 BASKET_CHANGED; concurrently removed sources or changed revisions may instead
return their normal 404/409. This is a point-in-time preview, not a reservation:
later checkout must recheck again.

## Confirmed memory and activity

The current enabled, unexpired buyer profile supplies hard per-item budget,
type, location and exclusion constraints. A larger total basket budget cannot
override them. The planner never writes preferences, enables consent, renews
profile expiry, or treats a basket budget as a remembered per-item limit.

Favorites and the existing bounded recent backend-verified sandbox purchase
signals are loaded only with active consent and only for the supplied public
candidates. They break equal-cost ties and never justify paying more, violating
a filter, accepting quality warnings or exceeding stock. Existing activity
bounds/errors and refund exclusions still apply. See
[personalization consent, scope and retention](buyer-personalization.md).

## AI explanations and saved follow-ups

The existing POST /api/v1/assistants/buyer and buyer conversation scope now
accept either listing_ids or basket. Existing listing requests still work.
Empty scopes or supplying both are validation errors. Basket contains the
same BasketRequest object above.

Illustrative one-shot assistant request:

~~~json
{
  "question": "Explain this basket and the constraints I should review.",
  "basket": {
    "storefront_id": "80000000-0000-4000-8000-000000000001",
    "budget": "40.00",
    "needs": [
      {
        "group_id": "bread",
        "quantity": 2,
        "alternatives": [
          {
            "listing_id": "70000000-0000-4000-8000-000000000001",
            "expected_listing_revision": 1
          }
        ]
      }
    ]
  }
}
~~~

Illustrative saved conversation creation:

~~~json
{
  "request_id": "90000000-0000-4000-8000-000000000001",
  "scope": {
    "role": "buyer",
    "basket": {
      "storefront_id": "80000000-0000-4000-8000-000000000001",
      "budget": "40.00",
      "needs": [
        {
          "group_id": "bread",
          "quantity": 2,
          "alternatives": [
            {
              "listing_id": "70000000-0000-4000-8000-000000000001",
              "expected_listing_revision": 1
            }
          ]
        }
      ]
    }
  }
}
~~~

Subsequent turns use the existing request_id, expected_revision and question
shape. The saved scope fixes buyer-approved needs, quantities, total budget
and candidate revisions. A follow-up can explain those choices and updated
stock/preferences; it cannot silently change the scope from free text.
A changed shopping request needs a reviewed new conversation scope. Stale
published revisions must be reviewed before a new scope is created.

The assistant recomputes the deterministic plan and source fingerprint before
and after inference, and before saving a turn. The model receives qualitative
eligibility, selected public products, disclosed quality and limitations;
exact prices, totals and outcomes are rendered as deterministic response.facts.
It cannot create a cart from its own prose or perform a purchase. A real local
Ollama/Qwen3 explanation is optional; failure returns the established explicit
assistant errors without inventing a fallback AI answer.

Saved owner-bound follow-ups use the existing dialogue/restart mechanics.
Changed stock/preferences/activity invalidate saved answers and prevent stale
model prose replay. Source withdrawal or stale revisions may block reads until
a new scope is reviewed. Owner deletion remains available independently of
source visibility. Existing 24,000-byte evidence, 65,536-byte answer and dialogue
bounds still apply; narrow an oversized basket scope rather than truncate it.

Profile erasure removes derived basket answers through the existing erasure
marker, including when a personalized plan was infeasible. Original questions
and explicit user-authored basket scopes have separate conversation deletion
and thirty-day inactivity retention. A memory proposal from a basket turn may
propose a budget only when the question explicitly says per-item or per listed
unit; total basket budgets cannot silently become per-item preferences. The
normal review/confirmation step remains mandatory.

## Frontend handoff and later enhancements

The frontend developer needs a storefront basket editor for quantities and
acceptable alternatives, optional merchandise budget, reviewable exclusions,
plan statuses and notices, deterministic facts/citations, and the saved
conversation browser integration. Display selling units and declared contents;
do not label a cheaper alternative as equivalent quality. For a ready plan,
review cart through /api/v1/orders/preview and obtain explicit confirmation
before the existing unpaid-order and PayPal sandbox workflow.

No browser integration or real payment has been performed by this backend PR.
Frontend acceptance of this additive contract remains pending.

Revisit multi-seller optimization as explicitly requested: compare merchandise
plans grouped into separate seller orders/pickups, expose those tradeoffs, and
keep travel costs unknown unless approved evidence exists. Decide any combined
checkout, settlement or payout changes separately; this follow-up does not
authorize a multi-seller payments platform. Other optional extensions include
package/unit normalization, splitting quantities, optional/prioritized needs,
larger candidate sets, richer buyer quality evidence and profile/scope editing.
Do not add them silently or claim the bounded minimum is a global market best.

## Validation

The related regression run passed 270 tests across baskets, assistants,
personalization, orders, storefronts and availability; 15 optional checks were
skipped, with one existing Starlette/httpx deprecation warning. The final affinity
label adjustment passed four focused memory/privacy checks. Two real local Qwen
checks passed: saved basket explanation/follow-up and remembered-preference
proposal/confirmation/explanation. Ruff lint and format checks passed for 373
Python files. All three documented JSON requests validate against the real
schemas, three affected OpenAPI operations require authentication, and 137 local
documentation links resolved. This does not claim a full backend-suite rerun,
universal model correctness, browser integration or payment validation.
