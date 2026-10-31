# FairMade API contract

## Status and common conventions

The account, seller-application, product, saved-analysis, and quality endpoints
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

Before frontend integration, jointly accept this proposal and agree on approved
development origins and browser credential handling. Public deployment requires
a separate account-security and operations milestone.
