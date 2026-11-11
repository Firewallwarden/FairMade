# Public marketplace ordering

Implemented additive backend proposal; frontend acceptance and browser integration
remain pending. The user chose transparent ordering from public quality-check
disclosures and comparable unit prices. Buyer-selected criteria/weights are
explicitly a later improvement (DOMAIN-009 in the
[decision register](local-mvp-decisions.md)).

This feature starts from current main and is independent of the open assistant,
forecasting and messaging PRs. It adds no database migration, provider, model,
account tracking or infrastructure.

## Where ordering applies

Optional sort is supported by:

- GET /api/v1/marketplace/listings.
- GET /api/v1/storefronts/{storefront_id}/listings.
- POST /api/v1/discovery/listings.

Modes are newest, price_asc, price_desc, quality, unit_price and value.
Catalog and storefront requests use query parameters. Nearby listing searches
use JSON fields in the existing transient-origin body. Nearby storefront search
is unchanged; this is ordering of products, not a quality score for stores.

Omitting sort preserves the existing default order and response fields:
publication recency for catalog/storefront listings, and nearest-first for
nearby listings. Explicit newest uses publication recency on every surface.
A storefront listing request now also accepts optional product_type.

For unit_price or value, supply both product_type and reference_unit.
Product types remain sourdough, eggs or other. Reference units are kg, l, egg,
loaf or item. Other modes omit reference_unit; a reference unit without an
explicit compatible mode is rejected. No mass/volume/count equivalence is
inferred from a product title or selling-unit label.

Illustrative catalog request:

~~~text
GET /api/v1/marketplace/listings?sort=value&product_type=sourdough&reference_unit=kg&limit=20&offset=0
~~~

Illustrative nearby request:

~~~json
{
  "origin": {"latitude": "0.00", "longitude": "0.00"},
  "radius_km": "10",
  "product_type": "sourdough",
  "sort": "value",
  "reference_unit": "kg",
  "limit": 20,
  "offset": 0
}
~~~

The coordinates are synthetic. Origins remain transient, omitted from the
response and never persisted. Returned seller approximate areas/distances keep
their established privacy and estimation limitations. An explicit product sort
changes listing order; an estimated distance is still shown but is not the
primary sort key.

Existing text/location/type/availability filters and current public visibility
apply before ordering. Storefront ownership stays scoped to its seller;
withdrawn profiles/publications/listings and sellers without access cannot
enter results. Private draft changes do not change approved ordering evidence.

## Exact and explainable policy

Only current approved public listing data and the published Passport's disclosed
quality_summary are read. Live private Quality Locks, undisclosed evaluations,
recipes, costs, purchase history, buyer preferences and contact information do
not influence ordering.

Quality status is one of:

- claims_match_unverified: the published check summary reports matching claims.
- undisclosed: no quality summary was approved for this public Passport.
- not_provided: the disclosed summary explicitly reports no supplied checks.
- needs_attention: the disclosed summary reports unresolved concerns, which may
  include failed, unknown or outdated evidence.

These are reported check states, not independent verification or a grade.
More checks, a larger evaluation count or an undisclosed private failure do not
produce a hidden quality score. A matching claim does not prove ingredients,
allergen suitability, welfare, safety or equivalent product quality.

Policy by mode:

| Mode | Ordering key |
| --- | --- |
| newest | Most recent approved publication, then stable listing UUID descending. |
| price_asc / price_desc | Published USD selling-unit price ascending/descending, then publication recency/UUID. Package sizes may differ. |
| quality | Unverified matching claims, then undisclosed/not-provided evidence, then needs_attention; recency/UUID ties. No price preference is added. |
| unit_price | Ascending published standardized unit-price display within the explicit requested product type/reference unit. |
| value | First disclosed quality-check group, then available stock before unknown stock, then ascending comparable unit price; recency/UUID ties. |

No weighted composite, objective fairness claim or universal value score is
created. This is an explicit lexicographic policy. Unit prices are exact Decimal
values from the approved six-decimal display, never binary floats or newly
invented precision. Equal displayed values tie by recency/UUID. Sorting never
changes the published selling-unit price charged at checkout.

For unit_price, missing prices, below-display-precision prices, incompatible
reference units or mismatching product types are not compared. Unknown or
below-precision values never become zero or win a cheapest-price comparison.

For value, needs_attention and known unavailable listings are also not compared.
Unknown quality remains explicitly unknown even if its unit price can be
ordered; it never becomes an established passing safety check. Unknown stock
is not assumed available and follows known availability within the same quality
group. Items with disclosed concerns are not acceptable savings recommendations.

Not-compared items remain visible after the ordered group, by publication
recency/UUID only. They are not ranked against each other by price or value.
This preserves visibility of legacy/incomplete data without presenting it as
an eligible saving. Render that group distinctly. When every item is uncomparable,
metadata explicitly reports zero compared items and a no-comparable-items notice.

## Additive metadata and pagination

An explicitly ordered page retains the existing items, limit and offset and
adds ordering. CatalogCard/detail payloads, approval hashes and Passport
disclosures do not gain ranking fields; ordering metadata is request-specific.

OrderingMetadata contains policy_version catalog-ordering-v1, mode,
product_type/reference_unit when selected, candidate_count, compared_count,
not_compared_count, notices and an items signal list for just the returned page.
Each signal has listing_id, quality_status, quality_basis
seller_reported_unverified, comparison_status ordered/not_compared and reasons.

Illustrative metadata (synthetic UUIDs and coverage, not actual seller claims):

~~~json
{
  "policy_version": "catalog-ordering-v1",
  "mode": "value",
  "product_type": "sourdough",
  "reference_unit": "kg",
  "candidate_count": 2,
  "compared_count": 1,
  "not_compared_count": 1,
  "items": [
    {
      "listing_id": "70000000-0000-4000-8000-000000000001",
      "quality_status": "claims_match_unverified",
      "quality_basis": "seller_reported_unverified",
      "comparison_status": "ordered",
      "reasons": []
    },
    {
      "listing_id": "70000000-0000-4000-8000-000000000002",
      "quality_status": "undisclosed",
      "quality_basis": "seller_reported_unverified",
      "comparison_status": "not_compared",
      "reasons": ["UNIT_PRICE_MISSING"]
    }
  ],
  "notices": ["Illustrative evidence ordering only; claims remain unverified."]
}
~~~

Counts describe the complete filtered candidate set, not just the page and not
a number of verified-quality products. Reasons are PRODUCT_TYPE_MISMATCH,
UNIT_PRICE_MISSING, INCOMPATIBLE_REFERENCE_UNIT,
UNIT_PRICE_BELOW_DISPLAY_PRECISION, QUALITY_REQUIRES_ATTENTION or UNAVAILABLE.

The complete filtered set is ordered before pagination, so this is not a
reordering of an arbitrary newest-first page. Explicit ordering is bounded to
1,000 candidates; overflow returns 409 ORDERING_SCOPE_TOO_LARGE and callers
must narrow filters. No truncated sample is silently described as the best.
This cap is an implementation limit, not a user-selected product restriction.
Nearby searches also retain their existing bounding-box/exact-radius source
limit and SEARCH_TOO_BROAD behavior. Ordinary omitted-sort browsing keeps its
existing pagination behavior.

Static ties are deterministic. Live republishing, visibility or stock changes
can reorder later requests; pages are not a persistent snapshot or stock hold.
No payment, price, preference, account or inventory changes occur during sorting.

All responses/errors use Cache-Control: no-store. Invalid enum/query/body
values and invalid cross-field scopes return the documented 422 validation
shape; GET scope errors identify the sort query and missing/incompatible
parameters. An overbroad ordered scope returns 409. Public browsing remains anonymous.

## Frontend handoff and later improvements

The frontend developer owns sort controls, required type/unit selection,
the separate not-compared group, quality-status/provenance labels, no-comparable
states, notices and existing pagination/filter interaction. Display disclosed
concerns and unknowns; do not label matching seller claims as certified,
or a policy order as objective “best quality” or “fairest price.”
The optional ordering page field is additive, but generated OpenAPI page model
names should be reviewed when regenerating frontend clients.

Option 2 is a later improvement: buyer-selected criteria/weights for personalized
ordering, with explicit consent, supported public evidence, missing-data rules,
hard quality constraints and evaluation before exposing a score. It is not
enabled by passing undocumented weights or requesting value ordering now.

Other follow-ups include indexed/scaled exact ordering beyond the current cap,
snapshot/cursor pagination for changing catalogs, richer public evidence and
historical quality freshness semantics. These entries authorize no external
data provider, new infrastructure or automatic scope expansion.

The user subsequently delegated recommended in-scope design choices during
the continuous cycle, with deeper alternatives retained as future improvements.
The specific grouping, tie and resource-limit details here are implementation
choices; the confirmed user choice is transparent evidence-based ordering.

## Validation

The affected regression suite passed 272 tests across ordering, catalog,
storefronts, discovery, availability, unit pricing and Passports. The final
cross-field validation/error-shape adjustment passed eleven focused checks.
One existing framework deprecation warning was reported. Ruff lint/format passed
for 294 Python files; 93 local documentation links, two schema-valid JSON
examples and three public OpenAPI operations passed. Tests cover withheld
private quality, exact decimals, incompatible/below-precision values, complete
scope pagination, visibility, availability and shared surface behavior. These
are backend checks, not a full-suite rerun or browser demonstration.
