# FairMade backend

The Fair Price Engine calculates batch and unit costs, fee-aware break-even
prices, seller-selected margin ranges, and profit simulations. The stateless
calculator remains available. Anyone can register a FairMade account and log in.
Accounts default to buyer; only accounts with verified seller access can manage
private products and save immutable analysis history. No AI or payment service is called.
Sellers can also define mandatory Quality Locks and save deterministic checks of
seller-entered alternatives. A passing check is not a quality certification.
Finished-product comparison endpoints store manually entered price observations
and normalize selected quotes to an explicit quantity, preserving source and
quality limitations. They do not establish a fair price.
Private seller pricing reviews assemble these saved records with deterministic
explanations, explicit unit mappings, and visible evidence gaps.
Seller-controlled Fair Price Passports provide private drafts, exact previews,
explicit approval, public snapshots, and withdrawal with hidden-by-default disclosures.

Use Python 3.11 or newer with SQLite 3.26+. From this feature's worktree root, create an isolated
environment, install the backend, migrate the database, and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn fairmade.main:app --reload --host 127.0.0.1
```

Interactive API documentation: <http://127.0.0.1:8000/docs>.
Machine-readable contract: <http://127.0.0.1:8000/openapi.json>.

```powershell
Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8000/api/v1/pricing/analyze' `
  -ContentType 'application/json' `
  -Body (Get-Content -Raw backend/examples/pricing-request.json)
```

Run checks from the worktree root:

```powershell
.\.venv\Scripts\python.exe -m pytest -c backend/pyproject.toml backend/tests
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
```

Run this milestone locally on 127.0.0.1. Public deployment, email verification,
password recovery, signup/login abuse controls, and backup operations are deferred.
No frontend is included. Browser credential storage must be agreed with the
frontend developer before integrating persistent login.

See [the calculator formulas](../docs/fair-price-engine.md), the
[API integration proposal](../docs/api-contract.md), and
[local account/application workflow](examples/seller-workflow.md).

## Local database and sessions

The default database is `fairmade.sqlite3` in the process working directory.
Set `FAIRMADE_DATABASE_URL` to a SQLite URL to override it; use the same
working directory and environment for migrations and the server. The app does
not auto-load .env files or create tables on startup. See [.env.example](.env.example).
Database files are ignored by Git and contain private seller data.

After pulling schema changes, run `alembic ... upgrade head` before starting
the server. Downgrading migrations deletes the affected tables and data.
Migration 0001 creates the original seller-only schema. Migration 0002 renames
the identity table to accounts and updates ownership/session references, preserving
IDs, password hashes, tokens, products, and analyses. It adds buyer roles for every
existing account plus the roles and seller-application tables. No old account is
automatically considered a verified seller; its private seller data remains stored
but inaccessible until seller access is granted after future verification.

Downgrading 0002 discards roles/applications and restores the old seller-only
access model. Use it only for deliberate local rollback.

Migration 0003 adds current Quality Locks and immutable evaluation records without
changing existing data. Downgrading it deletes only the Quality Lock and evaluation
tables. Run the same documented `upgrade head` command before using quality routes.

Migration 0004 adds immutable price observations and comparison reports. It leaves
existing identity, pricing, and Quality Lock data unchanged. Downgrading 0004
deletes only the two new comparison tables.

Migration 0005 adds immutable seller pricing reviews. Existing source records
are preserved. Downgrading 0005 deletes only review history.

Migration 0006 adds Passport drafts and publication snapshots. It preserves private
source evidence. Downgrading it deletes drafts and publication history.

## Seller-approved Fair Price Passports

Create a draft under `/api/v1/products/{id}/passports` using an owned pricing
review, an explicit public title and USD price, and an optional disclosure policy.
All cost, quality, and market disclosures default off. Public price is positive,
expressed in decimal-string USD cents, per the saved analysis's selling unit.

Load the private preview, then publish with its exact revision, preview hash,
and `approved: true`. The server reconstructs and checks the allowlisted payload
under a write transaction. A matching retry returns the existing publication;
stale or mismatched approvals return 409. Publishing a replacement supersedes the
previous public Passport for that product. Draft edits remain private.

Anonymous `GET /api/v1/passports/{publication_id}` returns only the approved
public DTO. Raw reviews, private source IDs, emails, cost-entry labels, labor
hours/rates, quote identities/references/locations, and private explanations are
never forwarded. Selected cost categories disclose per-unit totals only; labor,
total unit cost, quality requirements/summary, and market summary have separate
explicit switches. Server limitations and unverified labels cannot be removed.

Owners can withdraw publications; inactive versions return 404 publicly, with
no-store cache headers. Loss of seller access also hides public snapshots.
Withdrawal cannot erase copies already received by a client. Re-publication of
an inactive revision requires a new draft revision and fresh approval.

See [the Passport workflow](examples/passports/README.md). Source data remains
unverified; publishing does not certify quality or establish objective fairness.

## Explainable seller pricing reviews

`POST /api/v1/products/{id}/pricing-reviews` accepts a saved pricing-analysis
ID, optional comparison-report ID, and optional selected quality-evaluation IDs.
Every selected record must belong to the same owned product. No result, role,
verification basis, or other computed facts can be submitted by the client.

The review preserves the selected records, captured product/Quality Lock state,
and deterministic explanations. Quality failures, unknowns, and evaluations of
older requirements remain explicit. New reviews reassess quote age at the review
date using the earlier report's captured freshness cutoff; old reports and old
reviews never change. No LLM or external service is called.

Provide `production_unit_quantity` to declare the quantity represented by one
unit in the selected production analysis. Without it, the review shows comparison
context on its own basis but makes no cross-basis price assessment. There is no
parsing of the product's free-text selling_unit. Quantity conversions reuse the
comparison module; declarations such as a loaf's weight remain unverified.

Reviews provide list/detail reads and no edit/delete routes. They require seller
access and product ownership. Source versions unsupported by this review version
return 409. These are private seller payloads containing full costs and claims,
not buyer-facing Passport disclosures. They neither set prices nor establish
fairness, certify quality, or recommend lower-quality savings.

See the [synthetic review request and workflow](examples/reviews/README.md).

## Finished-product price evidence

Create observations through `POST /api/v1/products/{id}/price-observations`.
Supply a finished-product label/type, USD price and quantity, source name/kind/
reference, location, observation date, and optional quality/price notes.
All evidence is `seller_reported_unverified`; source references are stored as
plain text and never fetched. Future observation dates are rejected.

Use `POST /api/v1/products/{id}/price-comparisons` with explicit observation
IDs and a target quantity to save a comparison report. Supported units are g, kg,
egg, dozen, loaf, and item. Conversion is limited to compatible families (g/kg
and egg/dozen); loaf and generic item counts remain distinct, with no inferred
weights, sizes, or density. Decimal-string arithmetic rounds descriptive output
to six decimal places.

Reports capture the UTC comparison date and a configurable freshness cutoff
(0-365 days, default 30). Only selected, fresh, same-type, quantity-compatible
observations enter the range. Excluded quotes and their reasons remain visible.
Quality notes, locations, taxes/shipping/discount qualifications, and all source
inputs remain unverified; they are not normalized into equivalence.

Both observations and reports support paginated listing and detail reads, with
seller-role and product-ownership checks. There are no edit/delete routes.
Corrections require a new observation, followed by explicitly selecting the
appropriate IDs for a new report. Historical reports do not change as time passes.

See [synthetic finished-product examples](examples/comparisons/README.md).
This feature does not change pricing formulas or Quality Lock evaluation, certify
alternatives, recommend savings, or publish private seller data. Verification and
seller-role provisioning remain deferred.

## Quality Locks and evaluation history

Use `GET /api/v1/products/{id}/quality-locks` to load a product's current
revision and rules. PUT replaces the complete mandatory rule set and requires
`expected_revision`; stale edits return 409 instead of silently overwriting
another edit. Empty rules explicitly clear the set and still increment revision.

Evaluate an alternative through
`POST /api/v1/products/{id}/quality-evaluations` using a candidate label,
`expected_revision`, and typed claims. The backend saves the rules, claims,
checks, and status at that moment. Missing claims and incompatible types/units
are unknown; any failed mandatory rule fails the overall check. An empty rule
set is not evaluated, never an implicit pass.

These routes require seller access and product ownership, like pricing history.
Buyers, pending applicants, and admin-only accounts receive 403. Verification and
role grants remain deferred; automated tests use explicit synthetic seller grants.

See the [synthetic quality examples and workflow](examples/quality/README.md).
All claims remain `seller_reported_unverified`. No unit conversions, source
verification, price comparisons, or savings recommendations are made. Existing
pricing calculations retain their `QUALITY_NOT_EVALUATED` warning.

## Buyer defaults and seller applications

Registration and `GET /api/v1/auth/me` return `{id, email, roles}`.
Every registration starts with `["buyer"]`. Roles are additive, ordered as
buyer, seller, admin; admin alone does not grant seller privileges. Buying and
checkout endpoints are future features, not added by the role model itself.

An authenticated account can submit `{}` to
`POST /api/v1/seller-applications` and read its own pending request through
`GET /api/v1/seller-applications/me`. Submission returns 201, a repeat returns
the same application with 200, and an account already holding seller access
receives 409. A missing application returns 404.

Application submission does not grant seller access. Private product and analysis
routes now return 403 `SELLER_REQUIRED` for buyers, pending applicants, and
admin-only accounts. This is an authorization change from #5; frontend integration
must handle it.

Verification evidence, decisions, seller/admin role grants, admin provisioning,
admin monitoring APIs, and dashboards are deferred. New accounts cannot currently
become sellers through this API. The automated tests seed seller grants only to
exercise protected behavior; no public or development role-grant endpoint exists.

Login returns an opaque bearer token. Send `Authorization: Bearer <token>`
on private requests. Sessions expire 24 hours after login even if actively used.
Logout revokes only that token. Multiple logins create independent sessions.
Tokens cannot be refreshed; log in again after expiry. Only token hashes are
stored, and passwords are hashed with Argon2id. Never log request credentials
or save tokens in checked-in examples.

CORS is disabled by default. To permit browser development, set
`FAIRMADE_CORS_ORIGINS` to exact comma-separated origins approved for your
frontend, for example `http://localhost:5173`. Wildcards are rejected. No
cookie authentication is used.
