# Manual raw-material and supply ledger: local MVP

The user chose a manual quantity ledger after PR #31 opened and asked to retain
the deeper implementation for later. This is seller-reported inventory for local
development. It does not establish verified availability, cost, quality, expiry
or safety. Backend endpoints are implemented proposals pending frontend acceptance;
no frontend is included.

## Inventory boundary

Materials are private, seller-wide records, so flour or packaging can be tracked
without duplicating balances per product. The server assigns ownership and IDs.
Names are unique per seller after trimming and Unicode case folding. Different
grades/specifications need distinct labels and IDs; matching names never imply
ingredient equivalence, quality approval or a link to recipes/supplier inputs.

A new material starts at zero, revision 1. Record an explicit receipt or physical
count for existing stock. Name/notes can be replaced with an expected revision.
The unit cannot change. There is no archive/delete or ownership transfer API.
Stock and metadata changes both increment revision; history revision gaps may
represent metadata edits. Metadata edits preserve stock, and movements freeze
the material name/unit used when recorded.

Each stock event commits an immutable record and the resulting balance/revision
in one transaction. No stock event update/delete API exists; correct mistakes by
posting another reasoned event. A manual physical count can reconcile stock, but
does not independently prove what caused the discrepancy.

| Kind | Meaning of quantity | Balance effect |
| --- | --- | --- |
| receipt | Positive amount received | Add amount |
| usage | Positive amount consumed | Subtract amount |
| waste | Positive amount discarded | Subtract amount |
| adjustment | Nonnegative observed total count | Replace balance with count |

An adjustment at the existing balance is permitted as a recorded count confirmation.
Negative balances are rejected. occurred_on is a seller-supplied nonfuture date;
created_at is the server UTC recording time. Backdated entries apply to current
stock in posting/revision order; they do not reconstruct past balances or reorder
earlier events.

This ledger does not reserve/deplete materials from recipes, costings, purchases,
orders, refunds or sellable-product stock. It creates no pricing analyses, values,
supplier quotes, Quality Lock claims or public disclosures. Recipe costing remains
manual, as approved separately in MVP-018. Even matching labels do not create links.

## HTTP contract

Paths are relative to /api/v1/seller/materials. Every operation requires bearer
authentication and a current seller grant. Buyer/admin-only accounts get 403
SELLER_REQUIRED; missing sessions get 401. Missing/another seller's materials and
cross-material movement IDs return 404 without private payloads. Successful
private responses and material domain/validation errors use Cache-Control: no-store.
Validation errors omit submitted values.

| Method/path | Request | Success |
| --- | --- | --- |
| POST (base) | {name, unit, notes?} | 201 MaterialResponse |
| GET (base) | limit/offset | Page of owned materials |
| GET /{material_id} | None | MaterialResponse |
| PUT /{material_id} | {name, notes?, expected_revision} | MaterialResponse |
| POST /{material_id}/movements | MovementRequest | 201 MovementResponse; matching retry 200 |
| GET /{material_id}/movements | limit/offset | Page of MovementResponse |
| GET /{material_id}/movements/{movement_id} | None | MovementResponse |

Material name is trimmed, 1..200 characters; optional notes is trimmed text up
to 2,000 characters or null (default null). Material unit is g, ml or item and is
fixed for its lifetime. Duplicate creation/rename returns 409 MATERIAL_EXISTS;
repeating creation does not create another balance with the same normalized name.
PUT replaces all metadata; omitted notes becomes null. No quantity, owner, unit,
valuation or supplier field is accepted in PUT.

MaterialResponse: id, name, notes, unit, on_hand, revision, created_at, updated_at
and basis=seller_reported_unverified. Quantities are decimal JSON strings formatted
to six places. Internal scaled integers, normalized name keys and owner IDs are
not returned. Lists use limit 1..100 (default 20), nonnegative bounded offset
and newest created_at then UUID descending.

MovementRequest:

- expected_revision: strict positive integer, existing publication revision bound.
- request_id: client-generated UUID, stable across retries and scoped to material.
- kind: receipt, usage, waste or adjustment.
- quantity: finite nonnegative decimal JSON string, at most six decimal places
  and 1,000,000,000. Must be positive except for physical-count adjustments.
- unit: g, kg, ml, l or item. It must match the material's dimension.
- occurred_on: nonfuture seller-reported date.
- reason: trimmed, 1..2,000 characters without NUL. Keep secrets and sensitive
  third-party data out of this plain-text operational note.

Extra fields, including price, purchase_cost, role and owner fields, are rejected.
MovementResponse contains id, material_id, request_id, revision, kind, the frozen
material_name and canonical unit, before/after/delta decimal strings, the validated
original request JSON, server UTC created_at and seller_reported_unverified basis.
It contains no account credentials, private pricing data or payment records.
History orders by revision descending, then UUID, with the same bounded pagination.

Metadata and movement changes serialize in SQLite. Stale revisions return 409
REVISION_CONFLICT before changing stock. A matching retry returns the original
event even after later movements/renames, never applying it twice. Decimal spellings
such as 1 and 1.000000 are equivalent; unit/kind/date/reason/revision must match.
Reusing a key for different validated content returns 409 IDEMPOTENCY_CONFLICT.
New request IDs allow distinct intentional movements at the current revision.
Fetch the material separately for its latest balance after a historical retry.
All retries still require current seller authorization and ownership.

## Exact quantities and failure behavior

Stock uses integer millionths of the material's base unit, with no rounding.
kg becomes g and l becomes ml using the exact factor 1000. Counted items must be
whole numbers. Mass/volume/count never mix; there is no density or implicit
package/cup conversion. The maximum normalized amount/balance is 1,000,000,000
base units. The internal maximum of 1,000,000,000,000,000 is within SQLite's
64-bit integer range. Decimal formatting uses an isolated precision context.

An incompatible unit gives 422 UNIT_MISMATCH. A normalized input beyond the limit
gives 422 QUANTITY_LIMIT. A valid amount overflowing the current balance gives
409 QUANTITY_LIMIT; insufficient material gives 409 INSUFFICIENT_MATERIAL.
Invalid shapes, extra fields and numeric JSON quantities get redacted 422 errors.
Rejected/stale operations and failed commits leave balances, revisions and history
unchanged. Competing withdrawals cannot both use one revision or spend the same stock.

Migration 0021 adds materials and material_movements, ownership/history indexes,
unique name/retry/revision constraints and bounds/direction/unit checks. It preserves
earlier products, recipes, analyses and commerce data and creates no balances.
Downgrade preflights material/history and earlier protected records before DDL,
so a wider blocked rollback cannot partly drop schemas. Empty tables can roundtrip.
See the [synthetic workflow](../backend/examples/materials/README.md).

## Deeper implementation to revisit

Before production use that needs these capabilities, define lot/batch identity,
expiry and handling policies, traceability and recalls, multiple locations,
stock reconciliation/corrections and permissions, archiving/material merges,
record retention and audit monitoring. Quantity reports alone do not establish
that materials are usable or safe.

Inventory valuation needs separately approved receipt costs, fees/transport
allocation, supported currencies and a cost-flow policy such as FIFO or weighted
average. It must not silently replace manually entered recipe costs. Actual
production consumption needs explicit ingredient/material mappings, compatible
units, raw waste/usable yield, confirmed production events and atomic stock/yield
changes. Supplier-quote links, freshness and Quality Lock eligibility remain
separate future work. Reorder thresholds/alerts, forecasting, hosted operations
and frontend integration also remain open. These are tracked follow-ups, not
approval to select accounting policies, providers or new infrastructure.
