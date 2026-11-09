# Private supplier profiles and reported reliability

After PR #35 opened, the user chose **private records per seller**, rather than
shared community supplier ratings, and requested #28-#35 merge before this work.
Those PRs were individually refreshed, checked and verified squash-merged on main
before this feature began. Private visibility is a product policy, not a temporary
MVP limitation or a promise to publish later. See DOMAIN-002 in the
[decision register](local-mvp-decisions.md).

These backend APIs are implemented proposals pending frontend acceptance. No UI,
provider, shared supplier directory or public rating endpoint is included. Names,
ratings, dates, links and notes are seller-reported and unverified. A supplier
profile does not certify a real-world identity or product quality.

## Profiles and metadata history

All paths below begin /api/v1/seller/suppliers and require the existing bearer
session, current seller access and owner scope. Another seller's records and
source quotes are hidden as 404, including correction references. Buyer/admin-only
accounts receive 403 SELLER_REQUIRED; invalid/missing sessions receive 401 with
the existing bearer challenge. Successful responses and authorization/domain
errors use no-store; 422 details omit private raw input.

| Method/path | Success |
| --- | --- |
| POST (base) | 201 ProfileEventResponse; exact retry 200 |
| GET (base) | Page of ProfileResponse; optional archived=true/false |
| GET /{supplier_id} | Current ProfileResponse |
| PUT /{supplier_id} | 200 immutable ProfileEventResponse |
| GET /{supplier_id}/history | Page of immutable ProfileEventResponse |
| POST /{supplier_id}/experiences | 201 ExperienceResponse; exact retry 200 |
| GET /{supplier_id}/experiences | Page of ExperienceSummary |
| GET /{supplier_id}/experiences/{experience_id} | Immutable ExperienceResponse |
| GET /{supplier_id}/reliability | Current ReliabilityResponse |

Profile creation accepts request_id (UUID), name, optional location/notes and
archived (strict boolean, default false). Name/location are trimmed 1..200
characters; notes are at most 2,000. Names are case-insensitively unique within
one seller's catalog, including archives. Two sellers can keep separate records
with the same name. No global identity matching or contact collection occurs.

PUT fully replaces editable metadata and additionally requires expected_revision
(strict positive integer) and a nonblank reason of at most 2,000 characters,
without NUL. Omitted optional fields clear/default their values; read the current
profile before editing. Archival filters the catalog; it retains all history and
allows explicit reports of past experiences with a selected current revision.

Writes return a saved event: id, supplier_id, request_id, revision, reason, before
(null at creation), after (profile snapshot), created_at UTC and unverified basis.
The initial reason is "Initial supplier registration." Profile request IDs are
seller-scoped across create/replace. Exact retries return the same historical
event after later edits; different content/path under one key gives 409
IDEMPOTENCY_CONFLICT. Stale revisions give REVISION_CONFLICT; duplicate names give
SUPPLIER_EXISTS. SQLite account reservations refresh seller authorization and
serialize writes; metadata and event commit together. There is no delete API.

## Experiences and linear corrections

Experience POST accepts:

- request_id: UUID, scoped to this supplier; expected_supplier_revision: strict
  positive revision of the explicitly selected profile.
- label: trimmed 1..200 characters; observed_on: reported date no later than UTC today.
- rating: optional strict whole 1..5 score, representing this seller's opinion.
- promised_on/received_on: independently optional dates. Receipt cannot follow
  observed_on. A future promise can describe early receipt, but no future receipt
  or observation is allowed. One missing date makes delivery timing unknown.
- notes: optional private text up to 2,000 characters. At least a rating, a date
  or nonblank notes must be supplied; a label/quote alone is not an experience.
- source_quote_id: optional explicit UUID of an existing quote owned through the
  seller's product/sourcing input. It is a declared association, not independent
  verification that differently entered business names refer to the same supplier.
- corrects_experience_id/correction_reason: optional paired predecessor UUID and
  nonblank reason up to 2,000 characters without NUL.

A new report freezes the selected private supplier profile and, when linked, the
existing quote response. Nothing changes that quote, its prices/claims, a saved
comparison, inventory, recipe, payment, Passport or public listing. Later profile
edits and archives do not rewrite snapshots. Linking a quote is optional; names
are never used to infer links automatically or to share data with another seller.

Exact validated retries return their original immutable report before current
revision checks. Conflicting content returns IDEMPOTENCY_CONFLICT. Different
request IDs deliberately allow distinct reports with similar dates/labels; these
are not verified or deduplicated supplier orders.

A correction posts a complete replacement under a new request ID, with a reason
and the latest predecessor in this supplier's chain. Only one successor can
replace it; competing corrections get EXPERIENCE_ALREADY_CORRECTED. Corrections
preserve the original supplier snapshot and require its historical supplier
revision, even after the current profile changed. An unchanged quote reference
keeps its frozen snapshot; a different reference validates/fixes another owned
quote, and null clears it in the replacement. Originals remain readable.

Lists/summaries omit corrected predecessors by default. Experience lists accept
include_corrected=true for the full audit chain. observed_from/observed_until
inclusively filter seller-reported observation dates; reversed windows give 422
INVALID_DATE_RANGE. Correction exclusion runs globally before date filtering,
so moving a corrected observation outside a window does not resurrect its old
version inside the window. Results reflect current knowledge, not what the
platform knew at a historical date.

All pages use {items,limit,offset}, default limit 20, maximum 100 and the shared
bounded offset. Filters apply before pagination. Profiles order by created_at/UUID
descending; metadata events by revision descending; experiences by observed_on,
created_at and UUID descending. Summary pages omit large request/snapshot JSON.

## Exact, evidence-limited summaries

Reliability summaries return supplier_id, the applied observation-date window,
experiences_count, rated_count, average_rating, dated_deliveries_count,
on_time_count, late_count, unknown_delivery_count and on_time_fraction. Zero
observations give zero counts and null averages/fractions. Missing ratings are
excluded from the rating denominator. Only reports with both dates enter the
delivery denominator; receipt on/before the promise is on time, otherwise late.
unknown_delivery_count counts experiences without paired dates, not proven late
or outstanding orders. Rating-only/note-only reports do not depress the rate.

SQL returns integer counts/sums, never floating-point AVG. Division uses an
isolated Decimal context with precision 60, rounded half up to six places;
decimals are JSON strings. For scores 4 and 2, average_rating is "3.000000". One
timely and one late paired-date report gives on_time_fraction "0.500000" regardless
of additional unknown-date reports. A single aggregate query avoids loading
private snapshot blobs or querying each experience separately.

Every response labels seller_reported_unverified basis. Summary notices explain
that observations are private, possibly overlapping and unrepresentative;
ratings are opinions and missing dates are unknown. A high rating never overrides
a failed/unknown mandatory Quality Lock, verifies availability, establishes a
recommended substitution or enters an automatic price ranking.

## Persistence and scope boundaries

Migration 0024 follows 0023 and adds three tables, owner/history/date indexes,
case-insensitive name keys, revision/retry/correction uniqueness, bounded rating
and receipt-date checks, quote-snapshot pairing and foreign keys. No supplier,
score, receipt or identity association is inferred from old quotes. Empty new
tables can roll back to 0023 while preserving earlier livestock/production data;
new history blocks downgrade. Wider rollback checks earlier protected data before
any SQLite DDL, including the existing safe 0022 production preservation case.

See the [synthetic workflow](../backend/examples/supplier-records/README.md).
Current implementation choices include one subjective score per reported
experience, date-level delivery timing, manual records, one optional source quote
and one private profile namespace per seller. They are not additional confirmed
user policies. Separately scoped work could add procurement orders/receipts,
partial shipments, time zones, richer measures, duplicate reconciliation, evidence
and imports, comparison annotations, supplier aliases/locations, retention and
useful historical reports. Shared ratings/publication would require a new user
decision. Review frontend integration, backup/restore, retention, capacity and
concurrency for hosted use. No provider or infrastructure is authorized by this
follow-up list.
