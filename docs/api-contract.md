# FairMade API contract

## Status and common conventions

The account, seller-application, product, saved-analysis, quality, and comparison endpoints
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
| 409 | REVISION_CONFLICT | Stale Quality Lock replacement or evaluation request |
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

Before frontend integration, jointly accept this proposal and agree on approved
development origins and browser credential handling. Public deployment requires
a separate account-security and operations milestone.
