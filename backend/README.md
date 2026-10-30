# FairMade backend

The Fair Price Engine calculates batch and unit costs, fee-aware break-even
prices, seller-selected margin ranges, and profit simulations. The stateless
calculator remains available. Anyone can register a FairMade account and log in.
Accounts default to buyer; only accounts with verified seller access can manage
private products and save immutable analysis history. No AI or payment service is called.

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
