# Buyer and seller product pair suggestions

Implemented additive backend proposal; frontend acceptance and browser integration
are pending. Suggestions are read-only plans based on approved public listings.
They are not a new bundle SKU, discount, promotion, purchase or stock reservation.
No new package, migration, provider or infrastructure is introduced.

[Implementation #51](https://github.com/Firewallwarden/FairMade/pull/51) is a
main-targeted draft dependent on #38 through #46. Refresh and revalidate against
verified main after prerequisite integration before review readiness.

## Endpoints and request

POST /api/v1/buyer/bundles/suggest requires a current bearer session and another
seller's published storefront. POST /api/v1/seller/bundles/suggest additionally
requires current verified seller access and ownership of that published storefront.
Both accept the same JSON shape, illustrated with synthetic IDs:

```json
{
  "storefront_id":"10a466d2-3a96-424a-8aee-89dd8819df20",
  "candidates":[
    {"listing_id":"68d29540-15ee-42b8-b6e3-c85376cc2784","expected_listing_revision":1},
    {"listing_id":"f224b503-bea5-4a9c-bf82-e9d8acbcb020","expected_listing_revision":1}
  ],
  "budget":"25.00",
  "limit":3
}
```

Choose two through eight distinct listing IDs, all currently visible and owned
by the selected storefront's seller. Expected revisions must match current
approved revisions. limit is a strict integer one through four, default three.
Optional budget is a nonnegative, bounded USD decimal string with at most two
decimal places. It applies to the entire suggested pair's merchandise subtotal;
it is separate from any remembered per-item preference and is never auto-saved.
Unknown fields and malformed/bounded inputs return redacted 422 errors.

Responses include bundle_version same-storefront-pairs-v1, role, storefront_id,
budget, personalized, profile_revision, candidates, suggestions, eligible_pairs,
budget_excluded_pairs, history_start_date/history_end_date and notices. Dates
are ISO strings; money is USD decimal strings; IDs are UUID strings.
All private success/failure responses use Cache-Control: no-store.

Each candidate decision contains listing_id, eligible, exclusions and
affinity_reasons. Each suggestion contains exactly two current public listing
details, quantity_each one, subtotal, reasons, observed_copurchase_orders and
cart. The total is exact integer-cent addition of the two existing approved
prices. No model supplies arithmetic or invents a saving. eligible_pairs counts
all qualifying pairs before the response limit; at most twenty-eight pairs
exist under the eight-candidate scope. budget_excluded_pairs also includes pairs
exceeding the existing order amount ceiling. No candidate or quantity is silently
substituted to fit a budget. An empty suggestions list means no pair qualifies
within this request, not that the marketplace has no other options.

## Eligibility and ranking

Both roles exclude disclosed quality summaries requiring attention, missing or
unit-incompatible inventory, and insufficient available stock after existing
holds. Unknown stock is not treated as available. Missing quality evidence does
not certify quality, safety, ingredients, allergens or suitability. Suggestions
must preserve mandatory quality, safety and ethical requirements.

Buyer suggestions apply confirmed active profile budgets, product types,
location and exclusions as hard constraints. With active consent, favorites
and verified sandbox purchase affinity order eligible pairs; pair affinity is
the component-wise sum of each listing's established affinity tuple. Otherwise
no activity is queried. Ties use subtotal then stable listing IDs. These are
preference matches, not objective quality/value or semantic complementarity.
Buyer reports never read seller-private co-purchase history or other buyers'
personal activity. observed_copurchase_orders is null and history dates are null.

Seller suggestions rank eligible pairs by observed co-purchase order count,
then subtotal and stable listing IDs. Both products must occur in the same
order; quantities do not multiply the count. Evidence covers the previous ninety
complete UTC dates of backend-verified sandbox captures, excluding every order
with a refund request. Today's incomplete date is excluded. The query caps at
two hundred qualifying seller orders before candidate filtering; larger scopes
return 409 BUNDLE_HISTORY_TOO_LARGE rather than silently truncate. It selects
only order IDs/listing IDs internally and returns aggregate counts, never payer
details, buyer identities, order IDs or provider payloads. The count follows
listing identity across revisions: historical versions may differ from today's
products. Zero means no observed qualifying co-purchases, not no actual demand.
Patterns are not verified market demand, profit forecasts or a discount budget.
Sellers do not consume their buyer profile while planning their own products.

Buyer suggestions return ordinary two-line CartRequest payloads with quantity
one and current listing revisions. Review through POST /api/v1/orders/preview
before explicit order creation; listing prices and stock can change. Seller
suggestions return cart null. Both use only public approved listing/Passport
DTOs; no private recipe, cost, supplier, note or unapproved description is exposed
by this report. Taxes, fees and travel not modeled here remain unknown.

## Saved conversations and AI explanations

Buyer assistant questions and saved buyer scopes accept bundles with the same
BundleRequest shape. Choose exactly one scope: listing_ids, basket or bundles.
Seller questions and saved seller scopes accept optional bundles alongside
the existing required owned product_id. That product's listing must occur in
the supplied candidates; otherwise 409 BUNDLE_SCOPE_MISMATCH. A seller's other
selected private evidence remains governed by the existing seller scope.

```json
{
  "question":"Explain the suggested pair without assuming a discount.",
  "bundles":{
    "storefront_id":"10a466d2-3a96-424a-8aee-89dd8819df20",
    "candidates":[
      {"listing_id":"68d29540-15ee-42b8-b6e3-c85376cc2784","expected_listing_revision":1},
      {"listing_id":"f224b503-bea5-4a9c-bf82-e9d8acbcb020","expected_listing_revision":1}
    ]
  }
}
```

Use evidence title Current same-storefront product pair suggestions and current
response-local evidence keys. Exact subtotals and private seller counts render
as server-calculated facts; model context contains qualitative reasons, approved
product titles/types/disclosed quality and limitations. It omits exact totals,
co-purchase counts, raw activity and private order data. The model explains only
eligible suggested pairs; it cannot authorize purchases or invent compatibility.

Saved follow-ups retain scope, survive restarts and recompute current listings,
stock, preferences and applicable seller patterns each turn. Changed source
fingerprints withhold stale answers. Profile-derived buyer answers retain the
existing erasure marker even if no pair qualifies, so disabling/deleting profile
memory clears saved answer copies. Original questions follow conversation
retention separately. Preference proposals from bundle conversations require an
explicit per-item budget statement before proposing per-item memory; a total
bundle budget cannot silently become that preference.

## Errors and follow-up

401/403 apply to authentication/seller role. Foreign, unpublished or withdrawn
storefronts/listings use generic 404. Own-store buyer planning returns 409
SELF_PURCHASE; stale revisions return 409 LISTING_CHANGED. Report source changes
return 409 BUNDLE_EVIDENCE_CHANGED. Existing assistant/conversation inference,
source, access, response-size and retry guards still apply; no stale answer is
saved after inference-time changes. There is no LLM dependency for the two report
endpoints; assistant explanations use the existing opt-in local Qwen model.

The recommended foundation provides two-product same-storefront suggestions at
current prices. Later optional depth includes larger/configurable bundles,
seller-reviewed dedicated bundle products, evidence-backed complementary uses,
revision-specific historical patterns, confidence evaluation, cost/fee-aware
promotion budgets and explicitly approved discounts, and multi-seller plans.
None is required automatically for production or authorized by this note.
See DOMAIN-011 in [the decision register](local-mvp-decisions.md).
