# Manual recipes and batch costing: local MVP

The user chose manually entered ingredient quantities and purchase costs for local
development after PR #30 opened. Supplier-quote integration is deferred. These
are private seller reports, not verified receipts, supplier prices or quality
certifications. Backend endpoints are proposed for frontend integration; no UI
is included.

## Recipe and history

Each owned product has at most one current recipe in this MVP. Creating it is
explicit; GET does not write a row. A full replacement requires the current
revision and increments it. Instructions are private bounded plain text.

A costing explicitly saves the current recipe revision, ingredient allocations
and a normal immutable production-economics analysis in one transaction. The
analysis ID works in the existing analysis history, pricing-review and selected
sales-cost-basis workflows. Selecting it, approving disclosures and publishing
prices remain separate seller actions. Costing does not change stock, reservations,
orders, existing sales cost selections, Quality Locks, Passports or listing prices.

Edits do not mutate saved costings or analyses. Unsaved intermediate recipe edits
have no separate revision archive. There is no recipe/costing delete endpoint.
Per-product recipes avoid introducing a shared ingredient catalog before its
identity, allocation and inventory policies are agreed.

## HTTP contract

All paths below are relative to /api/v1/products/{product_id}/recipe. They require
a current seller grant and product ownership. Buyer/admin-only accounts get
403 SELLER_REQUIRED; another seller's or missing product gets 404. There is no
anonymous recipe endpoint. Successful reads/writes and recipe domain/validation
errors have Cache-Control: no-store. Validation errors omit raw input.

| Method/subpath | Input | Success |
| --- | --- | --- |
| POST (base) | RecipeCreate | 201 RecipeResponse; existing recipe: 409 RECIPE_EXISTS |
| GET (base) | None | 200 RecipeResponse; absent recipe: 404 |
| PUT (base) | RecipeCreate plus expected_revision | 200 RecipeResponse; stale revision: 409 |
| POST /costings | expected_revision and client-generated UUID request_id | 201 CostingResponse, exact retry: 200 |
| GET /costings | limit/offset | 200 Page of CostingSummary |
| GET /costings/{costing_id} | None | 200 CostingResponse; missing/cross-product ID: 404 |

RecipeCreate fields:

- name: trimmed, 1..200 characters; currency: USD; sellable_units: strict whole
  positive batch yield 1..1,000,000 in the product's selling unit.
- ingredients: 1..100 distinct labels (case-insensitive after trimming). Each has
  label, quantity consumed including batch waste, purchase_quantity, purchase_cost
  and cost_recorded_on. Quantities are {value, unit}; value and purchase_cost are
  finite decimal JSON strings, at most six decimal places and at most 1,000,000,000.
  Quantities must be positive; explicit zero purchase cost is allowed.
- Units: g/kg, ml/l or item. Item counts must be whole numbers. Consumed/purchase
  dimensions must match. No mass-volume, density, cup or implicit count conversion.
  Consumed quantity may exceed one purchase package; that does not imply a purchase.
- cost_recorded_on: a date supplied by the seller, not future on create/replace.
  It is not independent purchase evidence; there is no automatic freshness cutoff.
- other_costs: 0..100 existing pricing BatchCost entries. Materials are rejected
  here to prevent an additional material subtotal duplicating ingredients.
  Include only additional costs not already allocated in purchase costs or labor.
- labor: 0..100 existing pricing Labor entries; payment_fees and target_margin:
  existing modeled pricing settings. Fractional rates and maximum margin plus
  processing rate less than 1 retain the calculator's contract.
- proposed_prices: optional 0..50 decimal string amounts, default []; instructions:
  optional trimmed text up to 10,000 characters, default empty.

Unrecognized fields, including source/quote IDs, roles and ownership fields, are
rejected. Other costs, labor and fee settings retain the existing pricing validators.
Ingredient values and purchase costs use the stricter decimal-string validator.
The [synthetic bread and egg examples](../backend/examples/recipes/README.md)
provide full requests; example amounts are invented test data, not local prices.

RecipeResponse contains product_id, revision, content, created_at and updated_at
UTC. Revisions begin at 1; expected_revision is a strict positive integer with
the existing publication-revision bound. Concurrent edits cannot both use the same
revision successfully. A recipe edit does not change the product's timestamp.

CostingSummary contains id, product_id, request_id, recipe_revision,
pricing_analysis_id and created_at UTC. Details add the historical recipe_snapshot
and result JSON. Result includes manual-recipe-costing-v1 calculation_version,
USD, seller_reported_unverified basis, ingredient label/allocated_cost rows,
materials_total and explicit limitation/rounding warnings. These fields and recipe
instructions are private; no recipe payload is automatically published.

Costing IDs are scoped to the product. Summary pages omit large/private recipe
instructions and use limit 1..100 (default 20), offset>=0, newest created_at then UUID
descending. Missing recipes can have an empty history page.

The retry key is scoped to the product. An identical request_id/expected_revision
returns the original record even after later recipe/product edits; it never creates
a second analysis. Reusing the key for another revision returns 409
IDEMPOTENCY_CONFLICT. A new key with an outdated revision returns 409
REVISION_CONFLICT. Retrying after losing seller access still fails authorization.
New keys deliberately allow repeated costings of the same recipe revision.

## Allocation and rounding

For each ingredient:

    consumed cost = purchase_cost * consumed base quantity / purchased base quantity

Convert kg to g and l to ml by the exact factor 1000; items remain items. Include
raw waste in consumed quantity and count only sellable output in sellable_units.
Do not add that waste again as a separate material cost. Production output units
and ingredient units are distinct: the egg example yields 24 sellable dozens,
not 24 individual eggs.

Use an isolated Decimal context with precision 50. Round each allocated ingredient
cost half up to six decimal USD places once, then feed those exact displayed
allocations plus other costs/labor/settings into the existing pricing calculator.
Sum the rounded lines for materials_total. This aligns historical inputs, displayed
allocations and downstream cost/profit reports. Positive sub-micro allocations
rounding to zero produce a warning. A derived line exceeding the calculator's
1,000,000,000 limit is rejected 422 COST_LIMIT_EXCEEDED without saving a recipe.
There is no hidden AI calculation or final price choice.

Recipe costing is consumed production allocation, not whole-package cash spending,
an actual production event, stock depletion or a proof of sufficient materials.
Existing pricing warnings about unverified inputs, missing costs, market and
quality evaluation remain. This feature does not evaluate claims, suggest savings,
recommend substitutions or relax Quality Locks.

## Migration and future work

Migration 0020 adds product_recipes and recipe_costings, preserving earlier rows
and creating no recipe automatically. Foreign keys, positive revisions, unique
analysis links and product-scoped retry keys protect associations. An indexed
product/time/ID query supports bounded history. SQLite serializes creates, edits
and costing snapshots; failed commits roll back the analysis and provenance.

Downgrade preflights recipe/costing data and earlier protected history before any
DDL, preventing a wider rollback from partly dropping schemas. Blank recipe
tables can roundtrip while preserving existing products and analyses.

Before deeper production integration, design explicit selected-quote provenance
and frozen source snapshots, freshness/availability, usable yield versus consumed
waste, transport/bulk cash allocation, unit compatibility and quality eligibility.
Never silently replace a manual input with a cheaper quote or relax a Quality Lock.
Verification, provider integrations, prices and supplier identity need their own
approved evidence policies. Additional follow-up: shared ingredient identities,
multi-recipe/version management, receipt-backed costs, actual production/lot
traceability, inventory consumption and reconciliation, supported units/currencies,
cost update workflows, hosted operations and frontend integration. This list
records future work; it does not approve infrastructure, suppliers or new scope.
