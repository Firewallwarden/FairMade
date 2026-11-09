# Livestock groups, individual animals and production sources

The user chose **both groups and individual animals** after public-availability
PR #34. This is a product-model decision for detailed data, with no automatic
MVP/production expiry. Backend APIs are implemented proposals pending frontend
acceptance; no frontend is included. All livestock information is private,
seller-reported and unverified. Registration does not certify identity, health,
animal welfare, quality or ownership outside FairMade.

## Resource model and counts

Groups have a UUID, name, species, optional breed/notes, archive flag, revision,
server timestamps and optional reported_headcount/headcount_on. A count is a
strict whole integer 0..1,000,000, paired with its nonfuture observation date.
Omitting both means unknown; zero means a reported count of zero.

Group responses separately include registered_active_animals: the number of
active individually registered animals currently linked to that group. This is
registration coverage, not a verified census or an additional population. A flock
with reported_headcount 30 and 2 registered animals still reports 30, not 32.
The figures may disagree because registration is partial and observations age.
Registration, transfer and departure do not silently rewrite the reported count.
Animal membership does not increment the group's metadata revision.

Animals have a UUID, seller-unique identifier, optional name/breed/notes, species,
sex (unknown/female/male), optional born_on/acquired_on, active/departed/deceased
status, optional current group_id, revision and server timestamps. Dates cannot
be future; acquisition cannot precede a supplied birth date. Departed/deceased
animals must have group_id null. Unassigned active animals are supported.

Group names and animal identifiers are trimmed, case-insensitively unique per
seller, including archived/departed records. Species is fixed at registration;
membership requires matching case-folded species labels. There is no inferred
taxonomy, synonym matching or government tag verification. Names/species/breeds
and identifiers are 1..200 characters; notes are at most 2,000 characters.

## HTTP contract

Every route under /api/v1/seller/livestock requires the existing bearer session,
current seller access and resource ownership. UUIDs from other sellers are hidden
as 404, including group filters and production references. Buyer/admin-only
accounts receive 403 SELLER_REQUIRED; missing/revoked/expired sessions receive 401.

| Method/path under /api/v1/seller/livestock | Response |
| --- | --- |
| POST /groups | 201 HistoryResponse; exact retry 200 |
| GET /groups | Page of GroupResponse; optional archived=true/false |
| GET /groups/{group_id} | Current GroupResponse |
| PUT /groups/{group_id} | 200 HistoryResponse |
| GET /groups/{group_id}/history | Page of HistoryResponse |
| GET /groups/{group_id}/production-records | Page of ProductionSummary |
| POST /animals | 201 HistoryResponse; exact retry 200 |
| GET /animals | Page of AnimalResponse; optional group_id and status |
| GET /animals/{animal_id} | Current AnimalResponse |
| PUT /animals/{animal_id} | 200 HistoryResponse |
| GET /animals/{animal_id}/history | Page of HistoryResponse |
| GET /animals/{animal_id}/production-records | Page of ProductionSummary |

Create requests combine the profile fields, species and a change envelope:
request_id (UUID), occurred_on (nonfuture date), and reason (trimmed 1..2,000
characters, no NUL). PUT is a full replacement of editable fields, excludes
species, and adds expected_revision (strict positive integer). Omitted optional
fields clear their values/default; GET the current profile before editing.
Archiving a group with registered active members returns 409 GROUP_HAS_MEMBERS.
Linking to an archived group gives GROUP_ARCHIVED; species mismatch gives
SPECIES_MISMATCH. Move members explicitly first. Status/profile corrections and
unarchiving are allowed with a new reason and revision; old history stays intact.
There is no delete, animal sale/payment, or automatic headcount-adjustment API.

Writes return an immutable event: id, resource_id, request_id, revision,
occurred_on, reason, before (null on creation), after (profile snapshot), created_at
and seller_reported_unverified basis. Writes return the saved event rather than
today's profile, so an exact retry remains stable after later edits. Group event
snapshots contain profile metadata, not the live registration count. Read the
group separately for its latest registered_active_animals value.

Retry IDs are seller-scoped separately for group changes and animal changes.
Equivalent retries return their original event before checking current revision
or membership; different content/path under a reused key gives 409
IDEMPOTENCY_CONFLICT. Stale edits give REVISION_CONFLICT. Name/tag collisions give
GROUP_EXISTS/ANIMAL_EXISTS. SQLite writes reserve the owning account and recheck
the seller grant, membership and revisions. Profile and event commit together;
failed writes leave neither a change nor a consumed retry key.

History orders by recording revision descending. occurred_on is a seller's
reported date; created_at is server UTC. Backdated reports apply to the current
profile in recording order: this is not an effective-dated historical census.
Lists use {items,limit,offset}, default limit 20, maximum 100 and bounded offset.
Profiles order by created_at/UUID descending; filters apply before pagination.
Private responses and HTTP errors use no-store, preserve bearer challenges, and
validation errors omit raw private input. Unknown request fields are rejected.

## Production attribution

POST /api/v1/products/{product_id}/production-records additionally accepts optional
livestock_source: {kind: group|animal, id: UUID, expected_revision: integer}.
Omitting/null preserves existing unsourced behavior. One report selects one
source; it does not simultaneously allocate group output to a list of animals.
The product and selected livestock must belong to the authenticated seller.
Revision checks prevent attribution to a profile that changed since selection.
Archived/departed/deceased sources can be selected for reports of past production.

Detail adds livestock_snapshot (null without a source): kind, group and/or animal
profile snapshots, recorded_at, basis and an uncertainty notice. An individual
source also freezes its current group, if any. These are profiles at recording
time, **not proof of membership during the production period**. A new correction
with an identical source reference keeps its predecessor's frozen snapshot even
after membership/revision changes. A different reference explicitly selects and
validates a new snapshot; null clears attribution in the replacement. Originals
remain immutable. Legacy requests without the new key still retry correctly.

Source histories list attributable reports across owned products. Group history
includes direct group reports and individual reports whose frozen group matched.
Animal history includes only direct reports for that animal. Default pages omit
corrected predecessors; include_corrected=true shows them. Source membership
changes do not move earlier production history between groups. Summaries omit
large private request/cost/profile blobs. Reports can overlap: these pages are
not automatically additive output, cost or profit statements. No per-animal yield
is invented by dividing group output or counting current members.

## Persistence and further work

Migration 0023 follows 0022 and adds five tables: groups, animals, two immutable
event histories, and one source row per attributed production record. It adds
owner/history/membership/source indexes, retry and identifier uniqueness, bounded
count/status/date checks and foreign keys. Existing production requests/results
are preserved without fabricated attribution. Empty new tables can roll back to
0022 while retaining earlier production. New livestock data blocks downgrade;
wider downgrades preflight earlier protected history before SQLite DDL.

The feature changes no stock, recipes, pricing, payments, Quality Locks, Passports
or public listings. No provider, paid service or new infrastructure is used.
See the [synthetic workflow](../backend/examples/livestock/README.md).

Current implementation limits, rather than new user choices: exact species-label
matching, one current group per animal, manual profile observations, one source
per production report and existing whole selling-unit outputs. Separately scoped
future work can cover effective-dated membership/count reconstruction, explicit
measured allocations across multiple sources, genealogy, health/feed/veterinary
records, taxonomy/tag evidence, attachments/imports and useful reporting. Review
retention, backup/restore, capacity, concurrency and frontend integration before
hosted operation. These follow-ups are not automatically required by production
deployment or approval to add a provider or automatic inventory effects.
