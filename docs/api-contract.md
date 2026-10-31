# FairMade API contract

## Status and common conventions

The account, seller-application, product, saved-analysis, quality, comparison, review, Passport, marketplace, inventory, order, and sandbox-payment endpoints
below are implemented by the backend for **local development**. Their shared integration contract is
**proposed; frontend acceptance and browser integration are pending**. No frontend
changes are included. The existing stateless calculator retains its #2 behavior.

**Authorization change from #5:** registration now creates a buyer account.
Private product/history endpoints require the seller role and return 403 until
that access is granted after verification. Account responses add `roles`; the
OpenAPI identity schema is now named `AccountResponse` rather than `SellerResponse`.
Frontend integration must review these changes before relying on this proposal.

Base URL for local development: `http://127.0.0.1:8000`. Send JSON bodies with
`Content-Type: application/json`. UUIDs are JSON strings. Timestamps are UTC
ISO 8601 strings with a timezone. Unknown body fields are rejected. OpenAPI at
`/openapi.json` and interactive docs at `/docs` describe the implementation.

Money uses USD decimal strings; rates are fractional decimal strings. Saved
analysis requests use the existing [pricing contract](fair-price-engine.md)
without additional fields. No floating-point calculation or currency conversion
is introduced. Selling units are seller-defined labels, not automatic conversions:
if the unit is "dozen eggs", yield and prices must be expressed per dozen.

## Accounts and sessions

| Method and path | JSON request | Success |
| --- | --- | --- |
| POST /api/v1/auth/register | `{email, password}` | 201: `{id, email, roles}` |
| POST /api/v1/auth/login | `{email, password}` | 200: `{access_token, token_type, expires_at}` |
| POST /api/v1/auth/logout | No body; bearer required | 204, empty body |
| GET /api/v1/auth/me | Bearer required | 200: `{id, email, roles}` |

Email is validated, outer whitespace removed, and the entire address case-folded
for uniqueness and login. Passwords are 12-128 characters, used verbatim including
leading/trailing spaces. Registration does not log in. Email verification,
password recovery, account deletion, and email/password changes are deferred.

These are general FairMade accounts. Every registration receives `["buyer"]`.
Roles are additive and returned in buyer, seller, admin order. A verified seller
retains buyer capabilities; an admin does not automatically receive seller access.
Buying/checkout functionality itself remains future work. Clients cannot submit
roles, verification status, or identity fields when registering. Server-side
authorization reads persisted grants on each request rather than trusting the token
to contain role claims. Role grants and admin provisioning are deferred.

Successful login returns `token_type: "bearer"` and an opaque random token.
Send `Authorization: Bearer <access_token>` on every private request. Sessions
expire exactly 24 hours after creation; activity does not extend them. There
is no refresh endpoint. Logout revokes the current token, leaving other logins
active. Invalid, expired, or already revoked tokens receive 401 even on logout.
Only token hashes and Argon2id password hashes are persisted. Login responses
use `Cache-Control: no-store`.

Synthetic response shape; the token placeholder is not usable:

```json
{
  "access_token": "<token returned by login>",
  "token_type": "bearer",
  "expires_at": "2026-11-01T12:00:00Z"
}
```

Browser storage and a longer-lived "Remember me" experience are not part of this
backend milestone. CORS is off unless exact development origins are configured.

## Pending seller applications

| Method and path | JSON request | Success |
| --- | --- | --- |
| POST /api/v1/seller-applications | `{}`; bearer required | 201: SellerApplication, or 200 for the existing request |
| GET /api/v1/seller-applications/me | Bearer required | 200: SellerApplication |

Synthetic SellerApplication response:

```json
{
  "id": "8239b454-c4c6-40a6-87c2-2c855ad994a5",
  "status": "pending",
  "submitted_at": "2026-10-30T12:00:00Z"
}
```

The POST body is a required empty object. A request records intent only and
never verifies the applicant or grants the seller role. One application is
stored per account. Repeating submission returns the same ID and timestamp,
including concurrent retries. Existing sellers receive 409 `ALREADY_SELLER`.
GET returns 404 when the current account has no application. Only the current
account's application is accessible; there is no listing or ID-based lookup.

Ownership and status are server-controlled. Evidence fields, approval/rejection,
resubmission after a decision, privileged role grants, and admin application
monitoring endpoints are deferred. There is currently no API path from pending
to seller. Admin dashboards are a future frontend/backend integration.

## Private products

All routes require bearer authentication and the seller role. Buyers, pending
applicants, and accounts with only buyer/admin roles receive 403
`SELLER_REQUIRED`. Seller authorization precedes resource ownership lookup.
The server assigns ownership from the account; neither `seller_id` nor
`account_id` is accepted in requests or returned in product data.

| Method and path | Behavior | Success |
| --- | --- | --- |
| POST /api/v1/products | Create product | 201: Product |
| GET /api/v1/products | List this seller's products | 200: Page of Product |
| GET /api/v1/products/{id} | Read owned product | 200: Product |
| PATCH /api/v1/products/{id} | Edit supplied fields only | 200: Product |

Creation fields:

| Field | Required | Validation |
| --- | --- | --- |
| name | Yes | Nonblank, trimmed string, 1-200 characters |
| product_type | Yes | `sourdough`, `eggs`, or `other` |
| selling_unit | Yes | Nonblank, trimmed string, 1-200 characters |
| description | No | Trimmed string up to 2,000 characters or null; defaults to null |

PATCH uses the same fields, all optional. Omitted fields remain unchanged;
only description can be explicitly null. Empty PATCH is a valid no-op.
Names need not be unique. There is no product delete route.

Synthetic Product response:

```json
{
  "id": "7e1d8f97-680a-4205-b32d-c734b0c23936",
  "name": "Demo sourdough loaf",
  "product_type": "sourdough",
  "selling_unit": "loaf",
  "description": "Synthetic local development example; no verified product claims.",
  "created_at": "2026-10-30T12:00:00Z",
  "updated_at": "2026-10-30T12:00:00Z"
}
```

Lists accept `limit` (1-100, default 20) and `offset` (nonnegative,
default 0), returning `{items: [...], limit: 20, offset: 0}`.
Ordering is creation time descending, then UUID descending as a stable tie-breaker.
There is no total count; an empty items array indicates no records at that offset.

## Saved production-economics analyses

| Method and path | Behavior | Success |
| --- | --- | --- |
| POST /api/v1/products/{id}/analyses | Validate PricingRequest, calculate, save atomically | 201: Analysis |
| GET /api/v1/products/{id}/analyses | Paginated summaries | 200: Page of AnalysisSummary |
| GET /api/v1/products/{id}/analyses/{analysis_id} | Read complete immutable record | 200: Analysis |

All require bearer authentication, the seller role, and ownership of the parent product.
A mismatched product/analysis pair returns 404. Creation accepts the **direct**
PricingRequest body, not an envelope; see the synthetic
[request example](../backend/examples/pricing-request.json).
The backend calculates results; callers cannot submit an analysis result.

AnalysisSummary fields are `id`, `created_at`, and `calculation_version`.
Analysis adds `product_id`, `product_snapshot` (Product at save time),
`inputs` (validated PricingRequest), and `result` (stored PricingResponse).
Inputs include defaulted optional fields, such as an empty proposed_prices list.
Decimal values are stored and returned as JSON strings. Results retain the
calculator's warnings, unverified-input basis, assumptions, and version.

For the sample request, the stored result has batch_total `"100.000000"`,
unit_cost `"10.000000"`, break_even_price `"10.57"`, and the target range
`{"minimum":"13.32","maximum":"15.30"}`. These are calculated synthetic
examples, not validated seller costs or evidence of market fairness.

History lists use the same pagination and ordering rules as product lists.
Each successful POST creates a new record; retrying a successful POST can create
another record. Analyses cannot be edited or deleted through the API. Reads
return stored JSON without recalculating it under a newer calculator version.
Updating product metadata leaves historical product snapshots unchanged.

These records are private. There is no public passport, listing, or disclosure
endpoint in this milestone.

## Product Quality Locks

All quality routes require bearer authentication, the seller role, and ownership
of the parent product. Buyer, pending-applicant, and admin-only accounts receive
403; another seller's product returns 404. These endpoints remain a proposed
frontend integration contract.

| Method and path | Request | Success |
| --- | --- | --- |
| GET /api/v1/products/{id}/quality-locks | No body | 200: `{revision, rules}` |
| PUT /api/v1/products/{id}/quality-locks | `{expected_revision, rules}` | 200: `{revision, rules}` |
| POST /api/v1/products/{id}/quality-evaluations | `{candidate_label, expected_revision, claims}` | 201: Evaluation |
| GET /api/v1/products/{id}/quality-evaluations | Standard limit/offset query | 200: Page of EvaluationSummary |
| GET /api/v1/products/{id}/quality-evaluations/{evaluation_id} | No body | 200: Evaluation |

The initial GET returns revision 0 with empty rules and creates no database row.
PUT replaces the complete set, including when clearing it with `rules: []`.
Every successful PUT increments revision, even if the content is unchanged.
`expected_revision` is required on PUT and evaluation POST: a strict integer
from 0 through 2,147,483,646. A stale revision returns 409 `REVISION_CONFLICT`;
reload and review the rules before retrying. Evaluations and replacements
serialize at the database so the checked rules and stored snapshot agree.

All rules are mandatory. The backend never chooses or populates rules for a
seller. Each has a unique, trimmed `key` matching `^[a-z][a-z0-9_]{0,63}$` and
a trimmed, nonblank `label` up to 200 characters. At most 100 rules are allowed.

| Rule type | Additional fields | Matching behavior |
| --- | --- | --- |
| boolean | `expected`: JSON true/false | Exact yes/no equality |
| choice | `allowed_values`: 1-100 unique, trimmed, nonblank strings, each up to 200 characters | Exact, case-sensitive membership |
| numeric | `minimum` and/or `maximum`: decimal strings; `unit`: trimmed, nonblank string up to 200 characters | Inclusive bounds, with exact matching units |

Numeric bounds must be ordered and at least one must be present. Missing bounds
default to null in serialized rules. Numeric values must be finite decimal JSON
strings within -1,000,000,000 through 1,000,000,000 with at most six decimal places
(disregarding trailing zeros). JSON numbers and booleans are rejected as numeric
inputs. No unit conversion, aliases, or case normalization is performed.

Synthetic rule set, illustrating a seller preference rather than a recommended
production or safety standard:

```json
{
  "expected_revision": 0,
  "rules": [
    {"key": "organic_flour", "label": "Demo seller's flour requirement", "type": "boolean", "expected": true},
    {"key": "fermentation", "label": "Demo seller's chosen duration", "type": "numeric", "minimum": "24", "maximum": "48", "unit": "hour"}
  ]
}
```

## Immutable Quality Evaluation History

Claims form an object keyed by the rule's attribute key. Each claim has a required
`type` and `value`: a strict JSON boolean for boolean claims, a trimmed
nonblank string up to 200 characters for choice claims, or a decimal string
with an explicit `unit` for numeric claims. Numeric claims follow the same
bounds/precision limits as rules. At most 100 claims are accepted, and keys must
remain unique after trimming.

Every supplied key must be defined in the current rules; undefined keys return a
422 field error under `body.claims.<key>`. Omitting a configured attribute
is permitted and yields an unknown check. Malformed claims are rejected with 422,
while well-formed claims of the wrong type yield unknown. Unknown request fields
are rejected, including attempts to supply result/status/basis or weaken a rule
using a `mandatory: false` flag.

Synthetic candidate for the above rule set:

```json
{
  "candidate_label": "Synthetic alternative, unverified seller claims",
  "expected_revision": 1,
  "claims": {
    "organic_flour": {"type": "boolean", "value": true},
    "fermentation": {"type": "numeric", "value": "24.000001", "unit": "hour"}
  }
}
```

Candidate labels are trimmed nonblank strings up to 200 characters. The backend
calculates and stores the checks; callers cannot supply evaluated results.

Each check returns `key`, `label`, `status`, `reason_code`, and `message`.

| Check status | Reason codes |
| --- | --- |
| passed | MATCHED |
| failed | BOOLEAN_MISMATCH, CHOICE_NOT_ALLOWED, BELOW_MINIMUM, ABOVE_MAXIMUM |
| unknown | MISSING_CLAIM, TYPE_MISMATCH, UNIT_MISMATCH |

Aggregate status is failed if any check fails, otherwise unknown if any check is
unknown, otherwise passed. No configured rules yields not_evaluated with no
checks. No score or majority vote can override a failed mandatory requirement.

EvaluationSummary contains `id`, `candidate_label`, `rule_revision`,
`evaluation_version`, `status`, and `created_at`. Evaluation adds
`product_id`, `basis`, `rules_snapshot`, `claims`, and `checks`.
The current version is `quality-evaluation-v1`; the basis is always
`seller_reported_unverified`. Numeric strings, rule labels, candidate labels,
and all results are preserved in the saved record. List pagination and ordering
follow existing product/history conventions.

History is returned from stored JSON without re-evaluation. Later edits or clearing
rules never change old records. There are no update/delete routes for evaluations.
Repeating a successful POST creates another evaluation; no request-id deduplication
is implied. Mismatched product/evaluation IDs return 404.

**Interpretation:** passed means only that every supplied claim matches its rule.
The backend does not verify claim truth, certify quality, compare prices, recommend
an alternative, or establish acceptable savings. Missing or incompatible claims
cannot satisfy mandatory requirements. Existing pricing endpoints retain their
quality-not-evaluated warning and do not automatically consume these checks.

See the [synthetic sourdough and egg examples](../backend/examples/quality/README.md)
for integration calls and deliberately failed welfare claims.

## Finished-product price observations and comparisons

These private endpoints provide quantitative context from manually entered
finished-product quotes. They do not compare ingredient/supplier input costs.
All require bearer authentication, seller access, and ownership of the parent
product. Existing 401/403/404 conventions apply; admin alone does not grant access.

| Method and path | Behavior | Success |
| --- | --- | --- |
| POST /api/v1/products/{id}/price-observations | Save a manually entered observation | 201: Observation |
| GET /api/v1/products/{id}/price-observations | Paginate observation records | 200: Page of Observation |
| GET /api/v1/products/{id}/price-observations/{observation_id} | Read owned observation | 200: Observation |
| POST /api/v1/products/{id}/price-comparisons | Normalize explicitly selected evidence and save a report | 201: Report |
| GET /api/v1/products/{id}/price-comparisons | Paginate report summaries | 200: Page of ReportSummary |
| GET /api/v1/products/{id}/price-comparisons/{report_id} | Read complete stored report | 200: Report |

Observation creation accepts:

| Field | Requirement |
| --- | --- |
| label | Required trimmed nonblank string, at most 200 characters |
| product_type | Required source product type: sourdough, eggs, or other |
| currency | Required USD |
| price | Required nonnegative decimal JSON string |
| quantity | Required `{value, unit}`, with positive decimal-string value |
| source | Required `{name, kind, reference}` |
| location | Required seller-entered location label; not geocoded or verified |
| observed_on | Required date, not later than the current UTC calendar date |
| quality_notes | Optional string or null, up to 2,000 characters |
| price_notes | Optional string or null, up to 2,000 characters |

Source name and location are trimmed nonblank strings up to 200 characters.
Source kind is website, in_person, document, or other. Reference is a required
trimmed nonblank string up to 2,000 characters: for example a URL, receipt
reference, or observation description. References are **plain text**; the backend
does not fetch them, follow URLs, or verify any claims. Clients should not treat
these strings as trusted HTML or links.

Price and quantity must be finite decimal strings bounded at 1,000,000,000 with
up to six decimal places (disregarding trailing zeros). Price may be zero;
quantity must be positive. JSON numbers/booleans, negatives, nonfinite values,
unsupported currencies/units, unknown fields, and client-supplied verification
or ownership fields return 422.

Quantity units and exact conversion families:

| Family | Units and factors |
| --- | --- |
| Mass | g = 1 g; kg = 1,000 g |
| Egg count | egg = 1 egg; dozen = 12 eggs |
| Loaf count | loaf only |
| Generic item count | item only |

Count quantities must resolve to whole base counts: half a dozen is valid, half
an egg/loaf/item is not. Egg/dozen units require source product_type eggs; loaf
requires sourdough. Mass and generic item counts may be used for any declared
product type. There are no automatic aliases, weight-per-loaf assumptions,
density conversions, or equivalences between item, egg, and loaf. Equal counts
do not establish equal sizes or quality.

Observation returns `id`, `product_id`, UTC `created_at`,
`basis: "seller_reported_unverified"`, and `details` containing the
validated creation inputs, including defaulted null notes. Records have no
edit/delete routes. Use a new observation for a correction. Listings use standard
limit/offset pagination and creation-time-descending, UUID-descending ordering.

Report creation accepts:

```json
{
  "observation_ids": ["<UUID returned by observation creation>"],
  "target_quantity": {"value": "100", "unit": "g"},
  "max_age_days": 30
}
```

The placeholder is not a usable UUID. Select 1-100 unique observation IDs from
the same owned product; a missing, cross-product, or other seller's ID returns 404,
without identifying which resource exists elsewhere. The order is preserved.
The target quantity follows the same unit/value rules, including named unit
checks against the target product type. The free-text product selling_unit is
never parsed to infer a target weight, count, or package size.

max_age_days is a strict integer 0-365, default 30. The report captures the server's
current UTC date as as_of_date. Age equals as_of_date minus observed_on in calendar
days; an observation is stale only when age exceeds the cutoff. Thus a quote
exactly 30 days old is included at cutoff 30. A cutoff of zero means same-day
observations only. This is a configurable heuristic, not an assurance of current
availability or price accuracy.

For compatible families and matching source/target product types:

```text
normalized price = quoted price * target base quantity / quoted base quantity
```

Calculations use isolated Decimal precision of 60; only displayed output rounds
half-up to six decimal places. This is descriptive precision, not provider
settlement rounding or an executable offer; tiny positive amounts may round to
zero. There is no fee, tax, shipping, discount, or currency reconciliation.

Each result row contains the observation ID, full details, age_days, stale,
included_in_range, normalized_price, and exclusion_reasons:

- STALE_OBSERVATION: price remains normalized for inspection but is excluded.
- INCOMPATIBLE_UNITS: no conversion or normalized price is produced.
- PRODUCT_TYPE_MISMATCH: no normalized price is produced for a different type.
- FUTURE_OBSERVATION: defensively excluded if an imported record or clock change
  makes its date later than the comparison date; normal creation rejects it.

Multiple reasons may appear. The selected_price_range includes included_count,
excluded_count, and minimum/maximum normalized prices from only the selected,
fresh, same-type, quantity-compatible observations. If none qualify, bounds are
null and a no-comparable-observations warning is added. There is no average,
quality-weighted score, inferred local-market distribution, or fair-price verdict.

ReportSummary contains id, created_at, as_of_date, and comparison_version.
Report adds product_id, basis, request_snapshot, product_snapshot, and result.
The version is finished-product-comparison-v1. Results preserve the target
quantity, cutoff, comparison date, rows, range, and warning codes:

- UNVERIFIED_INPUTS
- QUALITY_NOT_EVALUATED
- LOCATION_NOT_VERIFIED
- TAX_SHIPPING_DISCOUNTS_NOT_NORMALIZED
- SELECTED_OBSERVATIONS_NOT_A_MARKET_SAMPLE
- PRICE_RANGE_IS_NOT_A_FAIRNESS_OR_SAVINGS_RECOMMENDATION
- NO_FRESH_QUANTITY_COMPARABLE_OBSERVATIONS, when applicable

Quality and price notes are preserved, not independently assessed. Reports do not
apply Quality Locks or certify an alternative. Inclusion in the range means only
date/type/quantity compatibility; even matching product types can differ in
quality, size, package conditions, geography, and availability. A cheaper quote
is not an acceptable-savings recommendation.

Reports are immutable and read from stored JSON without re-normalizing or aging
their observations on later reads. New evidence, a different cutoff, or a changed
comparison basis requires a new report. Repeating a successful POST creates
another record. Previous pricing and Quality Lock APIs remain unchanged, including
their market/quality-not-evaluated warnings.

See the [synthetic bread and egg examples](../backend/examples/comparisons/README.md).
The new endpoints are implemented by the backend; frontend contract acceptance
is pending.

## Explainable seller pricing reviews

These private reviews assemble explicitly selected saved evidence. They are not
public Fair Price Passports and contain seller cost details and claims.

| Method and path | Behavior | Success |
| --- | --- | --- |
| POST /api/v1/products/{id}/pricing-reviews | Assemble selected evidence and explanations | 201: Review |
| GET /api/v1/products/{id}/pricing-reviews | Standard paginated history summaries | 200: Page of ReviewSummary |
| GET /api/v1/products/{id}/pricing-reviews/{review_id} | Read complete stored review | 200: Review |

All routes require bearer authentication, seller access, and ownership of the
product. Every selected source record must also belong to that same product.
Missing, cross-product, and other sellers' evidence returns generic 404, with no
partial review saved. Existing 401/403 behavior applies.

Creation fields:

| Field | Required | Meaning |
| --- | --- | --- |
| pricing_analysis_id | Yes | UUID of one saved production-economics analysis |
| comparison_report_id | No | UUID of one saved finished-product comparison; defaults null |
| quality_evaluation_ids | No | Up to 100 unique selected UUIDs; defaults empty |
| production_unit_quantity | No | Explicit quantity represented by one production unit; defaults null |

A quantity uses the existing comparison `{value, unit}` contract. It requires a
comparison report, and named egg/dozen/loaf units must match the **saved pricing**
product type. Unknown fields, duplicate quality IDs, invalid IDs/quantities,
client-supplied results, and unsupported ownership/verification fields return 422.

The unit declaration is a seller-supplied assertion, not a verified measurement.
For example, declaring one production unit as 500 g lets the review normalize
selected 100 g quote evidence onto that basis. The backend never parses
selling_unit or infers a loaf weight, package size, or count equivalence.
Without a declaration, comparison context stays on its original basis and
there are **no** price relations against production-unit prices.

Review v1 supports production-economics-v1, quality-evaluation-v1, and
finished-product-comparison-v1 source records. Unknown versions return 409
`UNSUPPORTED_EVIDENCE_VERSION`. No new source analysis/evaluation is created
implicitly and no original calculation is overwritten.

ReviewSummary contains id, created_at, reviewed_on, and review_version. Review
adds product_id, basis, request_snapshot, evidence_snapshot, and result.
The version is seller-pricing-review-v1; basis is seller_reported_unverified.
The snapshot contains the selected saved pricing analysis, quality evaluations,
optional comparison report, and the product/Quality Locks captured during assembly.
Full cost inputs, source notes, original warnings, and unverified bases remain visible.

The result contains:

- economics: the selected saved pricing response, with costs, break-even,
  seller-margin range, scenarios, assumptions, and warnings. It is not recalculated.
- quality: captured rule revision and selected candidate checks. Overall status
  is not_provided, needs_attention, or claims_match_unverified. Failed, unknown,
  unevaluated, or outdated checks cannot be outweighed by other matching claims.
  A check applies to the captured rules only when both revision and snapshot agree.
- market_context: the selected comparison reassessed at reviewed_on, optional
  price relations, and an evidence status.
- explanations: deterministic `{code, message}` statements grounded in the
  selected facts and limitations. No LLM or external provider is used.
- warnings: stable codes identifying unverified inputs, missing evidence,
  outdated/failed quality checks, changed product metadata, and other limits.

Market-context statuses are not_provided, product_type_mismatch, basis_missing,
no_comparable_evidence, or comparable. Product-type mismatches between saved pricing
and comparison snapshots prevent numerical assessments. New reviews recheck quote
age against reviewed_on (UTC date), using the captured comparison cutoff. They
preserve quote notes/exclusions and do not modify the earlier report.

With a valid quantity mapping and fresh compatible evidence, the review assesses
break-even, seller-target range bounds, and proposed scenario prices as below,
within, or above the **six-decimal displayed** selected quote range. Each entry
contains metric, price, displayed_range_relation, and scenario_index (null except
for scenario prices). These relations describe that range; they do not establish
an optimal price, profit guarantee, affordability, or objective fairness.

Quality candidate evidence is not automatically linked to the compared quote IDs.
The review does not establish equivalent quote quality or filter those prices
using unrelated candidate checks. Matching claims remain unverified. A failed
mandatory candidate check is explicitly unsuitable as evidence of an acceptable
saving. The seller retains pricing control and no price is changed automatically.

Missing evidence is supported and explicitly flagged. A request containing only
pricing_analysis_id yields an economics review with missing-quality and
missing-comparison warnings. Saved source warnings, such as MARKET_NOT_EVALUATED
inside the original economics calculation, remain unchanged even when the
review adds a separate quantitative context section.

Review reads return stored snapshots and explanations without reassessing age,
quality revisions, or prices. There are no edit/delete routes; repeated successful
POSTs create separate reviews. Use a new review for newly selected or updated
evidence. History pagination and tie-breaking match existing APIs.

See the [synthetic review workflow](../backend/examples/reviews/README.md). These
endpoints are implemented backend-side; shared frontend acceptance is pending.
Publishing any review data requires a separate seller-approved disclosure feature.

## Seller-controlled Fair Price Passports

Passports project an owned saved pricing review into an explicit public schema.
Raw reviews are private and are never public Passport payloads.

| Method and path | Behavior |
| --- | --- |
| POST /api/v1/products/{id}/passports | Create a private draft (201) |
| GET /api/v1/products/{id}/passports | Paginate owned drafts |
| GET /api/v1/products/{id}/passports/{draft_id} | Read owned draft |
| PUT /api/v1/products/{id}/passports/{draft_id} | Replace complete content with expected_revision |
| GET /api/v1/products/{id}/passports/{draft_id}/preview | Inspect exact allowlisted payload and hash |
| POST /api/v1/products/{id}/passports/{draft_id}/publish | Approve current preview (201, matching retry 200) |
| GET /api/v1/products/{id}/passports/{draft_id}/publications | Paginate private publication history |
| POST /api/v1/products/{id}/passports/{draft_id}/publications/{publication_id}/withdraw | Withdraw owned version (204, idempotent) |
| GET /api/v1/passports/{publication_id} | Anonymous read of active approved snapshot |

Private endpoints require seller access and product ownership. Missing or
cross-product drafts/reviews/publications return 404; buyers, pending sellers
and admin-only accounts receive 403. Public reads expose neither drafts nor
withdrawn/superseded versions, and also hide publications when their owner loses
seller access. They return the same 404 for inactive and unknown IDs.

Creation accepts review_id (UUID from the same owned product), title (trimmed
nonblank, at most 200 characters), price (positive USD decimal string, at most
1,000,000,000 with at most two fractional places), optional public_description
(up to 2,000 characters or null), and disclosures (defaults all off).
The public selling_unit and product_type come from the saved pricing analysis,
not inferred current metadata or arbitrary client unit substitutions.

Disclosure policy fields:

- cost_categories: up to eight unique CostCategory values, default empty.
  Publish only selected enum-category per-production-unit totals.
- include_labor: publish only per-unit labor total, never hours/rates/names.
- include_unit_cost: separately authorize total production cost per unit.
- include_quality_requirements: disclose the captured seller-defined rules.
- include_quality_summary: disclose status and aggregate failure/unknown/outdated
  counts, never candidate names, IDs, or raw claims.
- include_market_context: disclose only status, explicit quantity, included count
  and historical normalized range; no raw quote names, IDs, references or locations.

All switches are strict JSON booleans and default false. Unknown fields, duplicate
categories, unsupported price precision, and invalid IDs return 422. Raw cost-entry
labels, private review/product/account/source IDs, emails, margins, break-even,
scenarios, free-text private explanations, and full evidence dictionaries are not
available as disclosure switches.

A draft contains id, product_id, revision, created_at, updated_at and content.
It starts at revision 1. PUT requires the complete creation fields plus a strict
positive expected_revision (at most 2,147,483,646); stale edits return 409.
Edits affect the draft only, never an existing approved snapshot.

Preview returns draft_id, revision, preview_hash, and payload. The payload has
passport_version fair-price-passport-v1, basis seller_reported_unverified,
reviewed_on, product (explicit public title/description and saved type/unit),
price (USD amount), optional disclosed sections, and mandatory server notices.
Hidden sections and optional values are omitted rather than filled from private
data. Category/labor costs are descriptive per-unit amounts rounded half-up to six
decimal places. Public price is represented in cents. User-written descriptions
and rule labels are unverified text; clients must render them as text.

Publication requires:

```json
{
  "expected_revision": 1,
  "preview_hash": "<64 lowercase hexadecimal characters from preview>",
  "approved": true
}
```

The placeholder is not a usable digest. The backend reserves the write
transaction, verifies the current revision, rebuilds the allowlisted preview and
checks its canonical SHA-256 hash. Stale revisions, mismatched hashes and unknown
review versions return 409 (REVISION_CONFLICT, PREVIEW_MISMATCH,
UNSUPPORTED_REVIEW_VERSION). Empty or false approval is not accepted.

One public version is active per product, enforced by a database index.
Publishing a new revision/draft supersedes the prior active snapshot atomically.
An identical active-version retry returns the same publication with 200. Retrying
an inactive revision returns 409 PUBLICATION_INACTIVE; edit to a new revision and
approve its new preview. Supersession/withdrawal never changes the stored payload.

Private publication history contains id, draft_revision, state
(published/withdrawn/superseded), created_at, optional withdrawn_at, payload_hash
and the approved payload. The approving account is stored internally for audit,
not returned publicly. Anonymous read returns only id, created_at, payload_hash
and payload. Public success and inactive-error responses use Cache-Control:
no-store. Withdrawal removes API access; copies already received by a client
cannot be recalled.

Server notices always identify unverified/historical data, possible undisclosed
details, and absence of certification or an objective fairness verdict. Opting
into quality/market sections adds their limitations. A seller cannot remove these
notices or mark evidence verified. Public prices do not perform checkout or
promise inventory availability.

See [the draft/preview/approval workflow](../backend/examples/passports/README.md).
The new contract is implemented backend-side and remains pending frontend review.

## Seller listings and public marketplace

Backend-implemented for local development; frontend contract acceptance is pending.
A listing is separate from its seller's private product. Creating a listing does
not expose it publicly. A product has at most one listing, with its own public UUID.

| Method | Path | Access and behavior |
| --- | --- | --- |
| POST | /api/v1/products/{product_id}/listing | Seller owner; create private draft, 201 |
| GET | /api/v1/products/{product_id}/listing | Seller owner; current draft/state |
| PUT | /api/v1/products/{product_id}/listing | Seller owner; replace complete draft with expected_revision |
| GET | /api/v1/products/{product_id}/listing/preview | Seller owner; exact public projection/hash |
| POST | /api/v1/products/{product_id}/listing/activate | Seller owner; approve preview, 200 |
| POST | /api/v1/products/{product_id}/listing/deactivate | Seller owner; hide listing, idempotent 204 |
| GET | /api/v1/marketplace/listings | Anonymous; bounded browse/search |
| GET | /api/v1/marketplace/listings/{listing_id} | Anonymous; approved listing and Passport |

All private routes require the existing bearer token, seller role, and product
ownership. Missing resources and cross-owner/product Passport references return
404. Buyer/pending/admin-only accounts cannot manage listings; everyone may browse.

Creation takes only:

```json
{
  "passport_publication_id": "60000000-0000-4000-8000-000000000001",
  "seller_display_name": "Example bakery",
  "location": "Exampletown",
  "summary": "Synthetic local-development listing."
}
```

This UUID is illustrative. The Passport must be the currently published version
for that product, owned by an account with seller access. Display name is explicit
public text (1..200 characters), never populated from account email. Location is an
optional seller-entered label (1..200), not a verified address or geospatial search.
Summary is optional text (1..1000). Optional fields may be null. Whitespace is
trimmed; unknown fields, including client price/type/state fields, return 422.

The private response has id, product_id, revision, state (draft/active/inactive),
created_at, updated_at, nullable published_revision, and content. It starts at
revision 1. A duplicate product listing returns 409 LISTING_EXISTS.
PUT requires the complete content and strict expected_revision, with the same
bounds as Passport drafts; it increments revision. Stale edits return 409.
Draft edits do not change the current approved public content or searchable fields.

Preview returns listing_id, revision, preview_hash, and payload. The allowlisted
payload contains listing_version marketplace-listing-v1, product and price copied
from the approved Passport, explicit seller_display_name, optional location/summary,
passport_id, passport_payload_hash, and mandatory notices. No private account,
product, review, source, or draft IDs are included. The price is a USD decimal string
in whole cents; the backend also stores authoritative integer cents internally.
Clients must render seller content as text.

Activation requires the same expected_revision/preview_hash/approved:true body
as Passport publication. The server serializes the write, recomputes the current
preview and canonical SHA-256 digest, and rejects stale/mismatched approval with
409 REVISION_CONFLICT/PREVIEW_MISMATCH. Empty, false, or nonboolean approval returns
422. Activation records the approving account internally and atomically updates
the public snapshot and searchable fields. An identical active revision retry
returns 200 without changing its publication timestamp. Deactivation hides the
listing and increments revision once, invalidating prior approval; repetition is
204 without further changes. Reactivation requires a new current preview/approval.

Public browse returns the existing Page shape (items, limit, offset).
Each card has id, published_revision, published_at (UTC), payload_hash, and payload.
Detail adds passport, the same public publication shape from the Passport endpoint.
Inactive/draft/missing listings return 404. Responses use Cache-Control: no-store.

Browse parameters:

| Parameter | Behavior |
| --- | --- |
| limit / offset | Defaults 20 / 0; limit 1..100, offset >= 0 |
| q | Optional 1..200 characters; case-insensitive literal substring of approved title and display name |
| product_type | Optional sourdough / eggs / other |
| location | Optional 1..200 characters; case-insensitive exact match of approved location label |

Text filters are trimmed. Whitespace-only filters act as absent. Filters combine
with AND; percent and underscore are literal search text. Results sort by most
recent approval timestamp descending, then listing UUID descending for ties.
There is no distance calculation, relevance/quality ranking, or cross-unit price
ranking. Pagination is offset-based and may shift when the catalog changes.

Visibility always requires an active listing, its linked currently published
Passport, and current seller access. Withdrawal/supersession or loss of seller
access hides it immediately. Publishing a replacement Passport does not
automatically switch the listing; update its draft reference and explicitly approve
it again. Visibility may return if seller access is restored while both approved
records remain active. Approval notices identify unverified seller/location data
and explicitly avoid promises of inventory, delivery, fulfillment, or checkout.

See [the synthetic marketplace workflow](../backend/examples/marketplace/README.md).

## Sellable inventory and unpaid orders

Implemented for local development; frontend acceptance is pending. This slice
creates unpaid order drafts and stock holds, not PayPal orders or paid purchases.
Amounts are merchandise subtotals, not final payable totals. Shipping, tax,
fulfillment, refunds, and verified payment processing remain separate work.

| Method | Path | Access / result |
| --- | --- | --- |
| GET / PUT | /api/v1/products/{product_id}/inventory | Seller owner; current/replace stock |
| POST | /api/v1/orders/preview | Authenticated account; current cart subtotal, no stock hold |
| POST | /api/v1/orders | Authenticated account; atomic stock hold, 201 new / 200 retry |
| GET | /api/v1/orders | Authenticated account; own buyer history, Page |
| GET | /api/v1/orders/{order_id} | Authenticated account; own buyer detail |
| POST | /api/v1/orders/{order_id}/cancel | Authenticated account; cancel own unpaid order, 200 |
| GET | /api/v1/seller/orders | Verified seller; own received orders, Page |
| GET | /api/v1/seller/orders/{order_id} | Verified seller; own received detail |
| POST | /api/v1/seller/orders/{order_id}/cancel | Verified seller; cancel own received unpaid order, 200 |

All use existing bearer authentication. Seller accounts retain buying capabilities.
Buyer access does not require seller verification; admin alone grants no seller
rights. Cross-owner order/product IDs return 404, buyer access to seller routes 403.
Success and domain-error responses use Cache-Control: no-store.

### Stock quantities and revisions

GET returns product_id, configured, revision, nullable selling_unit, on_hand,
reserved and available. Unconfigured inventory is revision 0, configured false,
null unit and zero counts. PUT takes complete content:

```json
{"expected_revision":0,"selling_unit":"loaf","on_hand":20}
```

Quantities are strict whole sellable units (0..1,000,000), not grams or raw materials.
The unit is explicit seller text and must match the approved listing's selling_unit
exactly at ordering time; no unit conversions are inferred. Revision is a strict
integer 0..2,147,483,646 on input, incremented on every successful replacement.
Stale writes return 409 REVISION_CONFLICT. On-hand cannot be below active reserved
quantity (STOCK_RESERVED). To change the unit basis, first empty the existing stock
and allow/cancel any active holds (INVENTORY_UNIT_LOCKED otherwise).

reserved is derived from pending orders whose deadline is strictly later than
server time. available = on_hand - reserved. Order creation, cancellation and
expiration do not deduct on_hand. A later verified payment integration must
atomically consume stock and complete the order; no such endpoint exists yet.
Existing marketplace browse results do not promise availability.

### Cart requests and exact snapshots

Preview and creation accept the same strict body:

```json
{
  "items": [{
    "listing_id": "70000000-0000-4000-8000-000000000001",
    "expected_listing_revision": 1,
    "quantity": 2
  }]
}
```

The illustrative listing UUID must be replaced. A cart contains 1..20 unique
listing IDs with strict integer quantities 1..10,000 and a positive strict
expected_listing_revision (the approved published_revision, not a private draft
revision). All items must currently be publicly visible and belong to one seller.
Different sellers require separate orders (MULTIPLE_SELLERS); self-purchase is
rejected (SELF_PURCHASE). Missing/unpublished/withdrawn listings return 404.

The server reads authoritative approved integer-cent prices. A changed public
revision returns 409 LISTING_CHANGED; private listing edits do not change the
approved revision. Missing inventory, mismatched unit basis, and insufficient
available quantities return INVENTORY_NOT_CONFIGURED, INVENTORY_UNIT_MISMATCH,
or INSUFFICIENT_STOCK (409). Merchandise subtotal is capped at USD 1,000,000,000;
exceeding it returns 409 ORDER_AMOUNT_LIMIT. Client prices, totals, seller IDs and
order/payment state fields are rejected as unknown fields (422).

Preview has order_version unpaid-order-v1, items, subtotal (USD decimal-string
amount), and mandatory notices. Each item contains listing_id, published_revision,
quantity, unit_price, subtotal, and listing (the allowlisted approved catalog
content). Item ordering is canonical by listing UUID. All calculations use integer
cents; decimal strings preserve cents. Preview does not reserve stock and can
become stale before creation.

Creation requires an Idempotency-Key header containing a UUID. The key is scoped
to the buyer account. An identical cart with that key returns the original order
with 200, even if subsequently cancelled/expired or its listing is no longer
visible. Reordering items does not change retry identity. A different body using
the key returns 409 IDEMPOTENCY_CONFLICT. New keys create distinct order attempts;
reuse the original key after an uncertain network result.

Creation reserves all quantities and saves its snapshot in one transaction.
Insufficient stock or any other item failure leaves no partial order/hold.
SQLite serialized writes prevent competing buyers from reserving the same stock.
No new cache, background worker, or external provider is introduced.

### Order lifecycle and history

Order response fields are id, status, created_at, expires_at (UTC), and snapshot
(the exact saved preview content). No private product/account IDs, account email,
source evidence, or undisclosed costs are included.

Orders start pending_payment and expire exactly 15 minutes after creation.
Effective status is expired at or after expires_at. Expiry is derived on reads and
availability calculations, so no scheduled cleanup is required for stock release.
The database retains the historical deadline; expiry never means payment succeeded.
Cancellation returns cancelled and releases the hold immediately. Repetition is
idempotent; an expired order remains expired. Snapshots and amounts are unchanged.

Buyer and seller history use limit/offset (defaults 20/0, limit 1..100,
offset >=0), newest created_at then UUID descending. Historical order snapshots
remain visible to their participants if the listing/Passport is later hidden.
They retain only already-approved catalog content, not the full private review or
Passport costs. Revoked seller access denies seller views; a buyer can still read
their own buyer history. Order creation never confirms payment. The sandbox
payment slice below adds verified capture and stock consumption; fulfillment,
refunds and shipment are still unimplemented.

See [the synthetic order workflow](../backend/examples/orders/README.md). Rate
limits, abuse monitoring and hosted operational controls remain part of hosted
readiness; local order holds do not establish production checkout readiness.

## Shared-merchant PayPal sandbox checkout

Approved development mode uses one shared sandbox merchant. Production seller
onboarding and seller-connected PayPal accounts are separate future work.
The provider adapter fixes its host to https://api-m.sandbox.paypal.com; no live
mode, arbitrary provider host, client merchant selection, or card-data endpoint exists.
PayPal is disabled by default and credentials stay in server process configuration.

| Method | Path | Access / behavior |
| --- | --- | --- |
| GET | /api/v1/paypal/config | Anonymous; enabled, sandbox environment, shared mode, USD, optional public client_id |
| POST | /api/v1/orders/{order_id}/paypal-checkout | Buyer owner; create/read the one saved checkout, 200 |
| GET | /api/v1/orders/{order_id}/paypal-checkout | Buyer owner; cached payment record, 200 |
| POST | /api/v1/orders/{order_id}/paypal-checkout/capture | Buyer owner; verify approval, capture and re-read provider state |
| POST | /api/v1/orders/{order_id}/paypal-checkout/reconcile | Buyer owner; server-fetch existing PayPal order, no capture POST |
| GET | /api/v1/seller/orders/{order_id}/paypal-checkout | Verified receiving seller; cached payment record |
| POST | /api/v1/seller/orders/{order_id}/paypal-checkout/reconcile | Verified receiving seller; recover/verify existing payment |

Every POST requires exactly {}. Unknown fields are 422: clients cannot provide
provider order/capture IDs, amounts, currency, merchant IDs, payment status,
approval assertions, or credentials. Existing bearer authentication, seller gates
and participant ownership checks apply. Cross-participant IDs return 404.
All success/domain-error responses use no-store. Payment validation errors omit
submitted input values, like auth errors.

The frontend uses the public client_id for PayPal's supported sandbox SDK, asks
this backend to create checkout, and returns provider_order_id to the SDK for
buyer approval. After SDK approval it calls backend capture with {}. A frontend
callback, redirect, or approval alone never marks an order paid. Browser work and
joint frontend contract acceptance remain pending.

The backend sends only the saved merchandise subtotal, USD, configured shared
merchant, and internal order correlation identifiers to PayPal. It does not send
seller costs, recipes, account emails, or private pricing evidence. This demo
requests no shipping collection and performs no tax/shipping calculation. Amounts
are sandbox merchandise payments, not production-ready checkout totals.

### Verification, states and stock

Checkout response fields: order_id, environment sandbox, merchant_mode shared,
state, optional provider_order_id/provider_status/capture_id, amount (USD decimal
string), optional sandbox_fee/sandbox_net and verified_at (UTC). Raw provider
responses, payer information, OAuth tokens, server secrets, internal request IDs,
leases and merchant ID are not returned. SDK client IDs are public identifiers.
Fee/net fields are reported only when available and validated; they describe the
shared sandbox merchant, not actual seller payouts or verified seller profit.

Payment state is creating, ready, capture_pending, completed, failed or needs_review.
An authenticated server GET must establish matching provider order ID, CAPTURE
intent, one purchase unit, FairMade reference/custom/invoice IDs, configured
merchant, USD currency and exact saved amount. Paid settlement additionally
requires one full final COMPLETED capture and overall COMPLETED. Available fee/net
data must use the same currency, remain within gross, and reconcile when both
exist. Unsupported partial/refunded/mismatched data requires review.

Order status adds capture_pending, payment_review and paid to the original
pending_payment/cancelled/expired values. Frontends must handle these new states.
The immutable order snapshot remains the original unpaid quote, including its
historical notices; current order/payment status establishes the outcome.
The underlying order reservation state remains separate from payment records.

New checkout/capture requires an unexpired uncancelled order and unchanged visible
approved listings, including current seller access. Before any outbound capture,
the backend commits a durable capture intent. That order's stock remains held
after the original 15-minute deadline while capture is pending or requires review.
Cancellation is blocked for paid/pending/review payments with 409
PAYMENT_REQUIRES_RECONCILIATION. Creating a PayPal order alone does not extend holds.

Only a verified complete payment atomically deducts on_hand, increments stock
revision, saves the unique capture receipt, and removes the reservation by marking
payment completed. Repeats return the same receipt and never deduct stock twice.
Verified failed/voided results cancel the order and release the hold without
deducting stock. Unexpected completion without a recorded local capture intent
requires review rather than silently consuming stock on a cancelled/expired order.

### Retries and recovery

Create and capture use distinct durable server-generated PayPal-Request-Id UUIDs.
Checkout is unique per order. Calls use short committed database phases with a
60-second operation lease; external HTTP requests do not hold a database write
transaction. Concurrent operations receive 409 PAYPAL_OPERATION_IN_PROGRESS.
After a crash, wait for lease expiry and reconcile rather than creating a new order.

An uncertain create retries the same request ID and saved amount. Capture retries
first fetch PayPal's state; an already completed payment settles without another
POST. A capture timeout is not a decline: reconciliation can discover success.
Capture POST retries are bounded to a conservative six-hour window; afterward
only existing-payment reads/reconciliation are allowed. No webhook endpoint,
scheduled reconciliation worker, refund processing, or automatic manual-review
resolution is implemented. Never release uncertain holds simply because time passed.

| Status | Code | Meaning |
| --- | --- | --- |
| 409 | ORDER_NOT_PAYABLE / ORDER_LISTING_CHANGED | Cancelled/expired order or changed/hidden listing |
| 409 | CHECKOUT_NOT_READY / PAYPAL_APPROVAL_REQUIRED | Missing checkout or buyer approval |
| 409 | PAYPAL_OPERATION_IN_PROGRESS | Active/superseding operation lease |
| 409 | PAYPAL_RECONCILE_REQUIRED | Retry window elapsed or payment needs reconciliation |
| 502 | PAYPAL_UNAVAILABLE | Provider result unavailable; retry/read/reconcile safely |
| 502 | PAYPAL_VERIFICATION_FAILED | Response does not prove expected payment; review needed |
| 503 | PAYPAL_DISABLED / PAYPAL_MERCHANT_CHANGED | Missing setup or merchant differs from saved checkout |

Configure process variables using [the server-only template](../backend/.env.example)
and [sandbox setup/recovery guide](../backend/examples/paypal/README.md).
Automated tests use provider doubles/HTTP mock transports and make no real PayPal
calls. A credentialed sandbox approval/capture and browser integration are separate
manual checks; they have not been claimed as completed.

## Errors and existing endpoints

New application errors use:

```json
{"detail":{"code":"NOT_FOUND","message":"Resource not found."}}
```

| Status | Code / shape | Conditions |
| --- | --- | --- |
| 401 | UNAUTHORIZED | Missing, invalid, expired, or revoked bearer token |
| 401 | INVALID_CREDENTIALS | Validly shaped login with unknown email or wrong password |
| 403 | SELLER_REQUIRED | An authenticated account lacks verified seller access |
| 404 | NOT_FOUND | Missing resource, another seller's resource, or mismatched parent |
| 409 | EMAIL_EXISTS | Registration with an existing normalized email |
| 409 | ALREADY_SELLER | A seller attempts to submit a seller application |
| 409 | REVISION_CONFLICT | Stale Quality Lock, Passport, or listing revision |
| 409 | UNSUPPORTED_EVIDENCE_VERSION | A pricing review selects an unsupported source version |
| 409 | PREVIEW_MISMATCH / PUBLICATION_INACTIVE / UNSUPPORTED_REVIEW_VERSION | Passport approval conflicts |
| 409 | LISTING_EXISTS / PREVIEW_MISMATCH | Duplicate listing or mismatched listing approval |
| 422 | FastAPI field-error array in detail | Invalid fields, UUIDs, pagination, or malformed JSON |
| 405 | Standard FastAPI detail string | Unsupported methods, including history edits |

401 responses include `WWW-Authenticate: Bearer`. Credential validation errors
omit submitted input and exception context so passwords are not echoed.
Other 422 responses retain the existing FastAPI validation format. Unexpected
storage failures roll back the request transaction and produce server errors.

`GET /health` still returns `{"status":"ok"}` without database or authentication
checks. `POST /api/v1/pricing/analyze` remains unauthenticated, stateless, and
compatible with #2. Its response is never automatically saved.

## Local integration checklist

Use the [account workflow](../backend/examples/seller-workflow.md) to register,
log in, submit/read a pending seller application, and log out. Newly registered
accounts cannot create private products or save history while verification is
deferred; seller-feature tests use explicitly seeded grants. Migrate the
database before testing. Use the same database URL and working directory for
migrations and the server. Session revocation and saved data persist across restarts.

Migration 0002 preserves IDs, credentials, sessions, products and analyses,
renames the identity table to accounts, and assigns only buyer roles to existing
accounts. Existing private seller data remains preserved but role-gated.
Use SQLite 3.26+ for native table/column renames. Downgrading 0002 loses role/
application data and restores the prior seller-only access model.

Migration 0003 adds the current rule-set and evaluation-history tables without
changing existing rows or initializing quality requirements. Downgrading 0003
discards Quality Locks and quality history while retaining earlier application data.

Migration 0004 adds price observations and comparison reports without modifying
existing data. Downgrading it deletes only those two tables and their records.

Migration 0005 adds immutable seller pricing reviews without changing the source
records. Downgrading 0005 deletes review history only.

Migration 0006 adds Passport drafts/publication history and one-active-version
constraints. It leaves source evidence unchanged; downgrade deletes Passports only.

Migration 0007 adds listing drafts, approved catalog snapshots, and browse indexes.
It leaves prior data unchanged; downgrade deletes listings only.

Migration 0008 adds sellable inventory, unpaid orders, and order-line reservations.
It leaves earlier records unchanged; downgrade deletes these three new tables.

Migration 0009 adds sanitized payment records, durable retry IDs and leases without
changing historical snapshots. It refuses downgrade once payment records exist:
dropping them could erase payment knowledge and allow an unsafe repeat payment.

Before frontend integration, jointly accept this proposal and agree on approved
development origins and browser credential handling. Public deployment requires
a separate account-security and operations milestone.
