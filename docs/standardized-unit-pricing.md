# Seller-declared quantities and standard unit prices

The user chose option 2 after private supplier PR #36: **quantity and measurement
unit are required before publishing a new or updated listing**. Existing approved
listings remain visible. DISC-002 records this product policy; it is not a temporary
MVP shortcut or authorization to invalidate old approvals.

[PR #37](https://github.com/Firewallwarden/FairMade/pull/37) implements the backend
and shared HTTP proposal, validated by 1,098 backend tests. Frontend forms
must supply the quantity before activation and display normalized prices as
comparison information. Frontend acceptance/integration is pending; no frontend
files are changed. This feature is independent of private supplier PR #36.

## Quantity for one selling unit

Listing POST/PUT content adds optional selling_quantity:

```json
{"value":"500","unit":"g"}
```

It describes net product contents/count in **one** approved selling unit, excluding
packaging: for example, 500 g per loaf, 750 ml per bottle, or 12 eggs per carton.
It is not stock on hand, a cart quantity, recipe yield or a pricing-analysis batch.
The product's human selling_unit label remains unchanged and is never parsed to
guess a quantity. Private production-unit mappings and public market-context
comparison targets are not package-content declarations and are never substituted.

value must be a finite positive decimal JSON string, at most 1,000,000,000, at
most six decimal places and at most 64 input characters. JSON numbers, booleans,
zero, negatives and nonfinite values are rejected with redacted 422 errors.
Supported units are g, kg, ml, l, egg, dozen, loaf and item. Egg/loaf/item counts
must be whole in their base count; 0.5 dozen is six eggs, while 0.1 dozen is invalid.
Named egg/dozen units require an approved eggs product; loaf requires sourdough.
An incompatible named unit gives 409 SELLING_QUANTITY_MISMATCH. Generic item is a
separate count dimension, never silently equivalent to egg or loaf.

## Drafts, preview and publication

Incomplete drafts can still be created, read and replaced without quantity or
with null. This supports staged editing and old drafts. PUT remains a full content
replacement: include selling_quantity to preserve it; omission/null clears it in
the draft. Photos/examples now preserve this field explicitly.

GET /api/v1/products/{product_id}/listing/preview adds publication_blockers outside
the approved payload. It contains SELLING_QUANTITY_REQUIRED when the current draft
would require a new publication and lacks the declaration, otherwise it is empty.
An unchanged active legacy revision has no blocker for its exact idempotent retry.

POST .../listing/activate keeps the expected_revision/preview_hash/approved:true
body. After existing ownership, source visibility, revision and exact-hash checks,
a new publication without quantity gives 409 SELLING_QUANTITY_REQUIRED. No state,
photo links, public payload or search fields are published by that failed request.
Quantity, calculated price and relevant notices are included in the exact preview
and canonical hash that the seller approves. Edits invalidate older approvals.
Client-supplied computed prices and other unexpected content fields are rejected.

This is an approved **publication-validation change**: older frontend clients may
still save incomplete drafts, but publishing them now fails until they add the
declaration. Update seller forms and preserve quantity during photo/listing edits.
Use publication_blockers and domain error codes for actionable messages. Keep
the existing explicit approval of the complete preview; do not auto-approve a
guessed default quantity on the seller's behalf.

## Immutable public data and old listings

Approved CatalogContent retains marketplace-listing-v1 with additive optional
selling_quantity and unit_price. New publications include both. Public catalog
cards/details, storefront listing pages, nearby results and visible saved products
use the same approved data. New private draft quantities do not appear there until
explicit activation. The linked Fair Price Passport and its disclosure hash are
unchanged; unit pricing is additional seller-approved listing content.

Pre-feature approved payloads without these fields remain valid. Their persisted
payloads, hashes, revisions, timestamps, visibility and prices are not rewritten.
Read absence/null as unknown standard-unit price, not free and not an inferred
single item. Older unpaid-order snapshots remain readable. Existing visibility
rules still hide listings when their Passport or seller access is withdrawn.

An exact retry of an unchanged active legacy approval remains idempotent, including
its original timestamp. A new private revision, a replacement Passport, or
deactivation/reactivation requires a new approval with quantity. Deactivation
continues to hide the listing explicitly; grandfathering does not bypass that.

## Deterministic normalization and rounding

Unit conversion uses the shared exact registry, with Decimal precision 60:

| Declared dimension | Base amount | Price reference |
| --- | --- | --- |
| g/kg | grams; kg multiplied by 1000 | One kg |
| ml/l | milliliters; l multiplied by 1000 | One l |
| egg/dozen | eggs; dozen multiplied by 12 | One egg |
| loaf | loaves | One loaf |
| item | generic items | One item |

There is no density, loaf-weight, count-to-mass or generic-item equivalence
inference. Unit pricing does not establish similar quality, actual contents,
substitution eligibility or objective price fairness.

```text
normalized price = approved selling-unit price * reference factor / declared base amount
```

unit_price contains calculation_version standard-unit-pricing-v1, currency USD,
status, nullable amount, reference_unit, reference_quantity "1", and
seller_reported_unverified basis. Display amount rounds half up to six decimal
places and is a JSON string. For a $17 loaf declared as 500 g, the result is
$34.000000 per kg. A $4.80 dozen eggs gives $0.400000 per egg. Three items for
$10 gives $3.333333 per item. Tax/shipping/fees are not invented or reconciled.

If a positive result rounds to zero at display precision, status is
below_display_precision and amount is null/omitted, with a notice that the price
is not free. A genuinely zero approved selling price yields calculated with
amount "0.000000". Clients must handle status and unknown legacy metadata before
rendering a number. Future conversion/display-rule changes need versioning and
explicit publication of a new snapshot, not retrospective recalculation.

## Commerce, privacy and verification

Checkout still charges the approved price **per selling unit**. For two $17 loaves,
each containing 500 g, merchandise subtotal is $34, not $68. Inventory and order
counts remain whole selling units; no quantities are consumed or converted by
display normalization. In an order snapshot, items[].unit_price is the original
charge price, while items[].listing.unit_price is the standard comparison price.
Backend totals never trust a displayed normalized amount supplied by a client.

Seller endpoints retain current seller access and product ownership; buyer/admin
accounts cannot edit declarations, and another seller's resources remain hidden.
Private responses/authorization errors use no-store and validation errors omit
raw draft inputs. Computation uses only the approved Passport price/type and the
explicit listing declaration. Private cost, recipe, source and account data is
not disclosed or used to invent public quantities. Public quantities remain
seller-reported; no weighing, certification or source verification is claimed.

No migration, startup backfill, dependency, provider or infrastructure is added.
Existing JSON columns store the new explicit snapshots. Examples and meaningful
tests cover dimensions, count/precision bounds, exact hashes, publication failures,
legacy reads/retries/reactivation, cross-surface consistency, rollback/restart and
unchanged checkout amounts. Existing listing fixtures now declare synthetic
quantities; legacy tests separately seed genuine pre-feature snapshot shapes.
See the [synthetic workflow](../backend/examples/unit-pricing/README.md).

Buyer comparison endpoints, price sorting, quality/value ranking, currencies,
additional units and evidence verification remain separate work. These follow-ups
do not authorize changing disclosures, inventing equivalence or relaxing a
mandatory Quality Lock. The backend fields are not a claim of a completed browser
comparison experience.
