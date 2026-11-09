# Completed production records: local MVP

The user chose completed batches/production periods only after PR #32 opened.
The planned/in-progress/completed alternative is an **optional deeper enhancement
for later**, not an automatic requirement for production deployment.

These private reports capture a seller's claimed actual output and allocated
costs after production. They are not verified expenses, independent completion
proof, inventory or quality certification. Backend endpoints are implemented
proposals pending frontend acceptance; no UI is included.

## Inputs and calculations

POST /api/v1/products/{product_id}/production-records accepts:

- request_id: client-generated UUID retained for retries, scoped to this product.
- label: trimmed 1..200 characters; kind: batch or production_period.
- started_on/completed_on: dates in order, completed_on no later than server UTC
  today. Multi-day batches and single-day periods are both allowed.
- selling_unit: exact product selling unit, preserved as the output basis.
- total_units/sellable_units: strict whole counts 0..1,000,000; sellable <= total.
  They do not imply any eggs/dozens/loaves conversion.
- currency: USD. costs: up to 200 batch cost entries with label/category/amount.
  labor: up to 100 label/hours/hourly_rate entries. Both arrays are required;
  explicit empty arrays are accepted with missing-cost warnings.
- Amounts/hours/rates: finite nonnegative decimal JSON strings, at most six decimal
  places and 1,000,000,000. Numeric JSON values are rejected.
- notes: optional trimmed private text up to 2,000 characters, or null.
- corrects_record_id/correction_reason: optional paired correction fields.
  Reason is trimmed 1..2,000 characters without NUL.

Unknown fields, planned/in-progress status, roles, owners, prices and supplier
links are rejected. Allocated overhead, reserves, equipment and imputed labor
do not establish cash expenses. Include consumed materials/waste once; do not
duplicate labor or charge whole packages when only part was consumed.

Calculation shares existing exact production arithmetic: category sums plus hours
times hourly_rate, in an isolated Decimal context with precision 60. No payment
fees, margins, prices or recipe estimates are invented. Unit cost divides reported
total cost by actual sellable units; unsellable output is total minus sellable.
yield_fraction is sellable divided by total. Display rounds half up to six places.

Zero sellable yield preserves costs and gives null unit_cost plus a warning.
Zero total also gives null yield_fraction; entirely unsellable nonzero output has
yield_fraction zero. Empty/zero categories do not prove that no expense occurred.
Missing material, labor and overhead allocations remain visible warnings.

## Snapshots, retries and corrections

Each transaction saves immutable product, request and result snapshots. A new
record requires the current product's exact selling unit. Later product edits
cannot reinterpret earlier output or costs. Status is always completed and means
seller-reported completion; basis is seller_reported_unverified.

An equivalent validated retry returns the same record with HTTP 200; initial save
is 201. Different content under one product/request_id returns 409
IDEMPOTENCY_CONFLICT. Decimal spellings such as 10 and 10.000000 are equivalent.
Retries are resolved before current-unit checks, so later product edits do not
break them. Failed commits leave no record or reserved retry key. Different keys
intentionally allow separate batches with similar labels/dates.

To correct a report, POST a complete replacement with a new request_id, the prior
corrects_record_id and a correction_reason. The predecessor must belong to the
same owned product and have no successor. Only one correction can follow it;
further corrections target the latest record. Originals remain readable and
unchanged. There is no update/delete API. A correction preserves its predecessor's
historical product/unit basis even if the current product changed.

Default lists omit records with a successor, showing each chain's latest report
once. include_corrected=true includes the historical chain. This does not detect
unrelated duplicates, overlapping egg periods or shared costs; distinct reports
are not automatically an additive production or financial statement.

## Reads, authorization and errors

| Method/path under /api/v1/products/{product_id}/production-records | Success |
| --- | --- |
| POST (base) | 201 ProductionResponse; equivalent retry 200 |
| GET (base) | Page of ProductionSummary |
| GET /{record_id} | Immutable detail, including corrected originals |

All routes require bearer authentication, a current seller grant and product
ownership. Buyer/admin-only accounts get 403 SELLER_REQUIRED, missing sessions 401,
missing/another seller's products and cross-product record IDs 404. Corrections
cannot reference another product's or seller's private report.

Summaries contain id, product_id, request_id, label, kind, dates, selling_unit,
total_units, sellable_units, corrects_record_id, server UTC created_at, completed
status and unverified basis. Details add historical product_snapshot/request/result
JSON. Result includes completed-production-costs-v1 version, USD, basis, category
totals, labor_total, batch_total, unit_cost, unsellable_units, yield_fraction and warnings.
Summary queries select small metadata columns without reading large cost blobs.

Lists use limit 1..100 (default 20), bounded nonnegative offset, and completion
date/server time/UUID descending. Completion dates are seller-reported; created_at
is server recording time. include_corrected defaults false. Successful private
responses and domain/validation errors use no-store; validation errors omit raw input.
There is no anonymous production endpoint.

Unit mismatch gives 409 PRODUCTION_UNIT_MISMATCH; correcting an already replaced
record gives 409 RECORD_ALREADY_CORRECTED. Missing references give 404; malformed
requests give redacted 422 errors. SQLite writes serialize and refresh seller
access/ownership. Competing retries/corrections and failed commits preserve history.

## Boundaries, migration and optional work

Reporting does not deduct raw materials, add sellable stock, change recipe costs,
create pricing analyses, select sales cost bases, publish Passports or change
listing prices/orders/payments. Quality Locks and supplier claims are not evaluated.
This respects the approved manual-stock and manual-recipe boundaries.

Migration 0022 adds production_records, product/retry uniqueness, a unique correction
predecessor, product/self foreign keys, output/date checks and a completion-history
index. It preserves prior data and creates no reports. Downgrade preflights new and
earlier protected history before DDL. Empty tables can roundtrip while preserving
products/analyses. See the [synthetic workflow](../backend/examples/production/README.md).

The user explicitly deferred planned/in-progress/completed lifecycle management.
Planning, scheduling, assignments, in-progress costs, reservations, cancellation
and notifications are optional future work requiring a new decision. They are not
prerequisites merely because deployment moves beyond local MVP.

Other separately scoped follow-ups include actual/recipe comparisons, explicit
stock consumption/reconciliation, lot/flock/animal context, partial output units,
expense evidence/allocation, overlapping periods/shared costs, pricing/sales-cost
integration, history reporting, retention/operations and frontend integration.
They do not authorize automatic stock changes, verification, providers or infrastructure.
