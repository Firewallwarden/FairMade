# FairMade backend

The Fair Price Engine calculates batch and unit costs, fee-aware break-even
prices, seller-selected margin ranges, and profit simulations. The stateless
calculator remains available. Anyone can register a FairMade account and log in.
Accounts default to buyer; only accounts with verified seller access can manage
private products and save immutable analysis history. Local Qwen3 8B assistants
are opt-in and disabled by default; the core calculators never call AI.
PayPal sandbox calls are opt-in and disabled by default.
Order participants can now exchange private plain-text messages with cursor
history and retry-safe sends. Apply migration 0029; messages perform no commerce
or assistant action. See [order messaging and later pre-purchase inquiries](../docs/order-messaging.md).
Buyer personalization supports explicit opt-in, remembered preferences, favorites
and verified sandbox purchase signals. Buyer conversations reload that memory;
preference proposals from saved questions require confirmation. Apply migration
0028 and see [the buyer memory workflow](../docs/buyer-personalization.md).
Receipt images can now become private OCR/AI drafts and explicitly reviewed
expense records. Run migration 0027 and configure local Tesseract plus the
existing Qwen3 model. See [receipt setup, review and limits](../docs/receipt-expenses.md).
Receipt expenses do not automatically change production costs or inventory.
Seller assistant history questions can explain approved receipt totals by period
and category. See [scope and double-counting limits](../docs/assistant-receipt-expenses.md).
Seller and buyer assistant endpoints now explain scoped evidence through local
Ollama. Exact financial facts are rendered by the backend separately from AI
paragraphs; seller evidence is owner-scoped and buyers see approved disclosures
only. No cloud fallback or automatic business changes are added.
Saved owner-bound conversations now support follow-ups across restarts, current
evidence checks, deletion and thirty-day inactivity expiry. Run migration 0026;
see [the conversation contract and frontend handoff](../docs/assistant-conversations.md).
The original independent question endpoints remain stateless.
See the [assistant workflow](examples/assistants/README.md) and
[contract, evaluation and limits](../docs/local-assistants.md).
Seller assistant sales/history questions now reuse private sandbox sales totals
and bounded saved cost analyses. See [period semantics and limits](../docs/assistant-sales-history.md).
Selected supplier reports now explain current checks and exclusion reasons while
preserving eligible-only cost minima. See [supplier explanations](../docs/assistant-supplier-explanations.md).
Local AI can generate private description drafts from product metadata. Sellers
edit and approve exact copy before applying it to the private product; public
publication stays separate. Run migration 0025 and see
[the description workflow](../docs/ai-description-drafts.md).
Sellers can keep private supplier profiles, subjective ratings and dated delivery
observations with immutable corrections and exact summaries that show missing data.
Optional quote references freeze owned evidence without changing comparisons or
Quality Locks. See the [private supplier workflow](examples/supplier-records/README.md)
and [contract and limits](../docs/private-supplier-reliability.md).
Private per-product recipes now save manually entered ingredient quantities and
purchase costs, revision-safe edits and immutable costing snapshots. Each explicit
costing also saves a normal production analysis, without changing stock or prices.
See the [manual recipe workflow](examples/recipes/README.md) and
[contract, rounding and production follow-up](../docs/manual-recipe-costing.md).
Sellers can also maintain private raw-material/supply quantities with exact
receipt, usage, waste and reasoned physical-count history. Revisions and retry
keys protect changes; recipe costing and sellable stock remain separate.
See the [manual material workflow](examples/materials/README.md) and
[contract and deeper inventory follow-up](../docs/manual-material-inventory.md).
Completed production records now capture seller-reported actual output and
allocated costs, including zero-output runs and immutable linked corrections.
Default history shows the latest correction per report; stock remains manual.
See the [completed production examples](examples/production/README.md) and
[contract and optional future workflow](../docs/completed-production-records.md).
Private livestock tracking now supports both groups and individual animals,
observed headcounts distinct from registered members, revision-safe transfers,
and immutable history. Production reports can explicitly select one source and
freeze its profile without changing stock or attributing group yield to individuals.
See the [livestock examples](examples/livestock/README.md) and
[API contract and limits](../docs/livestock-tracking.md).
Sellers can also define mandatory Quality Locks and save deterministic checks of
seller-entered alternatives. A passing check is not a quality certification.
Finished-product comparison endpoints store manually entered price observations
and normalize selected quotes to an explicit quantity, preserving source and
quality limitations. They do not establish a fair price.
Private seller pricing reviews assemble these saved records with deterministic
explanations, explicit unit mappings, and visible evidence gaps.
Seller-controlled Fair Price Passports provide private drafts, exact previews,
explicit approval, public snapshots, and withdrawal with hidden-by-default disclosures.
Marketplace listing drafts add explicit activation/deactivation and anonymous
browse/detail APIs; approved Passports supply the public product identity and price.
See the [synthetic listing workflow](examples/marketplace/README.md).
New and updated listing publications require explicit selling quantities. The
seller approves the declaration and calculated price per kg/l/egg/loaf/item;
older approved snapshots remain visible with unknown unit pricing. Checkout
still charges per selling unit. See the [unit-pricing workflow](examples/unit-pricing/README.md)
and [contract and frontend impact](../docs/standardized-unit-pricing.md).
Public listings now include exact recorded available quantities after active
reservations, with availability filters for catalog, storefront and nearby
listing searches. Saved-product cards share the live projection. Unknown or
incompatible inventory is explicit; checkout still rechecks stock.
See the [availability workflow](examples/availability/README.md) and
[disclosure policy and contract](../docs/public-listing-availability.md).
Sellable inventory and unpaid buyer orders now support exact merchandise subtotals,
15-minute reservations, cancellation, and private buyer/seller history. Shared-merchant
PayPal sandbox checkout now adds verified capture, recovery, payment records, and
stock deduction after confirmation. Tax, shipping and delivery remain deferred;
private local pickup progress is tracked separately after verified payment.
See the [synthetic inventory/order workflow](examples/orders/README.md).
See [sandbox setup and payment integration](examples/paypal/README.md). Live
production will require seller-connected merchant accounts through a separately
approved integration; this adapter cannot call live PayPal.
Buyers can request a full refund of a verified paid order. The receiving seller
reviews the private reason and approves or denies; approval initiates a verified,
retry-safe sandbox refund. Refunds do not automatically restock goods. See the
[buyer request and seller review workflow](examples/refunds/README.md).
Private supplier comparisons now record seller-entered quotes for each ingredient
or material, apply input-specific requirements, and compare whole-package cash
outlay with cost per usable unit. Reports preserve quote and rule snapshots;
unknown or failed requirements never enter eligible cost summaries.
See the [synthetic supplier workflow](examples/suppliers/README.md).
Sellers can explicitly select a saved analysis as a product's private sales cost
basis. New orders freeze that estimate separately from buyer-visible data.
Private sandbox sales reports combine verified capture fees, completed refunds
and frozen costs, showing unavailable profit when required data is missing.
See the [sales reporting workflow](examples/sales/README.md).
All authenticated accounts can save private favorites from the public catalog.
Hidden listings retain the bookmark but expose no catalog content.
See the [saved-product workflow](examples/favorites/README.md).
Verified sellers can create one storefront profile for the local MVP, preview
and explicitly publish it, and withdraw it. Anonymous discovery shows approved
profile fields and the seller's currently visible listings.
See the [storefront workflow](examples/storefronts/README.md).

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
but inaccessible until seller access is granted through the approved review process.

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

Migration 0007 adds marketplace listings, approved public snapshots, and browse
indexes. Existing data is preserved; downgrade deletes listings only.

Migration 0008 adds sellable inventory, unpaid order snapshots, and order lines.
It preserves earlier data; downgrade deletes stock and orders only.

Migration 0009 adds durable PayPal request IDs, operation leases and sanitized
capture records. It preserves existing orders and inventory. Downgrade is blocked
if any payment records exist to avoid losing payment/retry history.

Migration 0010 adds refund requests, seller decision audit and sanitized refund
receipts without changing existing orders or captures. Downgrade is blocked once
any payment/refund records exist; keep financial history and migrate with the
server stopped.

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
alternatives, recommend savings, or publish private seller data. Seller access can
now be approved through the separate manual administrator review workflow.

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
Buyers, pending applicants, and admin-only accounts receive 403. Manual admin review
can grant seller access; isolated tests may still seed grants for unrelated features.

See the [synthetic quality examples and workflow](examples/quality/README.md).
All claims remain `seller_reported_unverified`. No unit conversions, source
verification, price comparisons, or savings recommendations are made. Existing
pricing calculations retain their `QUALITY_NOT_EVALUATED` warning.

## Supplier sourcing and comparison history

Create a sourcing input under a product, configure its own Quality Locks, and
record supplier quotes with provenance, usable yield, package limits, availability
and a flat transport charge. A comparison specifies the usable quantity needed
and current rule revision. It keeps failed/unknown/stale alternatives visible
while excluding them from cost summaries. An input claim match is unverified
and does not establish finished-product quality or recommend a substitution.

Migration 0011 adds three sourcing tables without changing earlier data. Run the
same documented upgrade command. Downgrade refuses if sourcing or financial
records exist, before SQLite DDL, to protect history and avoid partial rollback.
Supplier quotes and reports have no update/delete routes. Correct a quote by
creating another, and create a new report to reassess freshness or new rules.

These APIs are private and additive; frontend contract acceptance is pending.
Supplier discovery, ratings, external data integrations, AI recommendations,
automatic recipe changes and raw-material stock management are deferred.

## Private sales and estimated profit

Select an existing saved analysis through a product's `sales-cost-basis` endpoint,
using the current selection revision. An explicit null analysis clears it.
Analysis and product units/types must match; no latest-analysis fallback occurs.
New orders freeze that selection in the same transaction as stock reservation.
Costs use exact batch/yield ratios rounded once per order. Missing/incompatible
costs do not block checkout; older orders keep unknown costs.

`GET /api/v1/seller/sales` and its `/orders` detail page require verified seller
access. Supply UTC start_date (inclusive) and end_date (exclusive), 1-366 days
apart. Reports select completed captures verified during that period and reflect
completed refunds currently known, including later refunds. This is a sales-cohort
estimate, not a period cash-flow or bank/payout statement.

Original capture fees and modeled production costs are retained after refunds;
no stock is restored automatically. Unknown fees/costs or unresolved refunds
leave profit unavailable. Known subset totals include coverage counts. Summary
rejects periods with over 1,000 sales; narrow the period or use paginated detail.
Figures remain sandbox/shared-merchant data and seller-reported cost estimates.

Migration 0012 adds private selection/snapshot tables and a capture-time index
without backfilling old costs. Run the documented upgrade command before starting
new code. Downgrade refuses before SQLite DDL if cost selections/snapshots,
financial or sourcing records exist. Private costs are excluded from buyer orders
and public schemas.

## Favorites and saved products

Authenticated buyer/seller accounts can create, page, read and remove their own
favorites under `/api/v1/favorites`. Saving an already-visible saved listing
returns the same bookmark without changing its time. Hidden/unpublished listings
cannot be newly saved.

Reads return the current approved public card. If a listing/Passport is withdrawn
or superseded, or seller access is lost, the bookmark remains with
listing_visible=false and listing=null. No stale catalog or private content is
copied into it. Favorites do not reserve stock or prices.

Migration 0013 adds favorites/indexes without changing earlier records. Run the
standard upgrade command. Downgrade refuses if favorites or protected history
exists. Browser removal uses DELETE with explicit CORS origins. Shared pagination
rejects offsets outside SQLite's supported signed 64-bit range.

## Seller profiles and storefronts

The local MVP permits one storefront per verified seller account, with a stable
public UUID separate from account identity. Private plural collection routes
under `/api/v1/seller/storefronts` leave room for future multi-store support.
That future feature needs a cardinality/listing-assignment migration.

Draft content includes display name, description and an optional public location
label. Preview and approval publish only those explicit fields. Published drafts
can be edited without changing current public content until new approval;
withdrawal hides the profile and invalidates earlier approval revisions.
Seller-access loss also hides public storefronts.

Anonymous `/api/v1/storefronts` browse/detail and per-storefront `/listings`
show only current approved data. Private account details, draft edits and
economics never appear. Profiles are seller-reported and do not certify identity
or quality. Storefronts group current visible listings by account ownership.
Existing listing names/prices remain separately approved; withdrawing a
storefront does not deactivate those listings.

Migration 0014 adds one table and discovery indexes without creating/publishing
profiles for existing accounts. Downgrade refuses if storefronts or earlier
protected history exists. No paid services, frontend interfaces, contact lookup
or precise location data are introduced.

## Nearby seller and product discovery

Sellers can optionally add `approximate_area` (label plus latitude/longitude at
most two decimal places) to storefront drafts. The existing preview and explicit
approval publish this representative area point and update its index atomically.
Draft edits stay private until approval; published points are public and do not
certify an address or guarantee anonymity. Text location labels are not geocoded.

Anonymous read-only POST `/api/v1/discovery/storefronts` and `/listings` accept
transient origin coordinates, radius_km (1..500), optional text/type filters and
pagination. Responses include approved resources and estimated straight-line km,
nearest first. No buyer origin is saved or echoed; requests use bodies rather
than URL coordinates and responses use no-store. Search does not guarantee stock.
Only approved points/currently visible resources match; existing profiles without
points remain in regular browse. No maps or external service is introduced.

Migration 0015 creates the area index without changing prior publications or
inferring coordinates. More than 1,000 bounding-box candidates returns an explicit
SEARCH_TOO_BROAD error; narrow the search rather than using truncated results.
Downgrades stop before DDL when storefronts or earlier protected history exists.
See [the runnable examples](examples/discovery/README.md) and
[the contract](../docs/api-contract.md#approximate-area-nearby-discovery).
Future work includes location entry/precision policy and spatial-query scaling;
exact pickup locations require a separate explicit disclosure decision.

## Product photo uploads

Verified sellers upload raw JPEG/PNG bytes to `/api/v1/products/{product_id}/photos`.
Uploads are private, bounded, decoded and normalized into metadata-free JPEGs.
The photo repository stores immutable bytes/digests with metadata in the local
SQLite database, with atomic saves/deletions and per-product/account quotas.
Listing drafts may select up to six owned product photos with alt text and order;
existing preview/hash approval controls publication. Private changes never rewrite
approved images. Public image reads enforce current listing/Passport/seller visibility.
Deletion of photos referenced by a draft or active listing is rejected.

Install the new Pillow dependency and migrate through 0016 before using these
routes. Existing listing publications and hashes are unchanged. No frontend,
external media hosting or client filenames are introduced. Hosted media storage,
processor isolation, abuse controls and moderation remain follow-up work.
See [photo upload examples and limits](examples/photos/README.md) and
[the contract](../docs/api-contract.md#product-photo-uploads-and-approved-listing-images).

## Local pickup fulfillment

Verified-paid orders can have separate, private seller-reported pickup progress:
preparing → ready for pickup → collected. Only the order's buyer and current seller
can read instructions/history. Writes use optimistic revisions and append immutable
events without changing payment/stock or publishing a precise location. Pending or
approved refunds block progress; collection is terminal and remains unverified.
Migration 0017 preserves all existing order snapshots and does not backfill progress.
See [the contract and future plans](../docs/pickup-fulfillment.md) and
[synthetic examples](examples/fulfillment/README.md). Delivery/shipping, addresses,
fees/taxes, schedules/notifications, buyer-confirmed handoff, returns/restocking and
hosted retention controls remain separate future decisions.

## Verified sandbox purchase product reviews

General FairMade accounts can publish one review per purchased product after
backend-verified sandbox capture, without seller or pickup approval. Explicit
publication consent makes bounded rating/text immediately public on a visible
product. Authors alone can edit/withdraw/republish, with optimistic revisions.
Public reviews use a generic buyer label and expose no account/order/provider IDs.
Ratings and text remain unverified opinions, not quality or fairness certification.
Refunds do not automatically suppress feedback; catalog visibility still governs
the whole product page. Average ratings use exact integer/decimal calculations.
Migration 0018 preserves earlier records and guards destructive rollback.
See [the full contract and production follow-up](../docs/product-reviews.md) and
[synthetic examples](examples/product-reviews/README.md). Moderation, reporting,
appeals, abuse controls, privacy/retention, audit and frontend integration remain
future work. These buyer reviews are separate from private seller pricing reviews.

## Buyer defaults and seller applications

Registration and `GET /api/v1/auth/me` return `{id, email, roles}`.
Every registration starts with `["buyer"]`. Roles are additive, ordered as
buyer, seller, admin; admin alone does not grant seller privileges. Buying and
checkout endpoints are future features, not added by the role model itself.

An authenticated account can submit `{}` to
`POST /api/v1/seller-applications` and read its own request/outcome through
`GET /api/v1/seller-applications/me`. Submission returns 201, a repeat returns
the same application with 200, and an account already holding seller access
receives 409. A missing application returns 404.

Application submission does not grant seller access. Private product and analysis
routes now return 403 `SELLER_REQUIRED` for buyers, pending applicants, and
admin-only accounts. This is an authorization change from #5; frontend integration
must handle it.

Manual administrator review now provides an explicit pending-to-approved/denied
workflow. Approval atomically records the reason/audit and adds seller while
retaining buyer. Administrators cannot decide their own applications, overwrite
final decisions or implicitly gain seller access. Shared reasons and status are
visible to applicants; reviewer identities remain admin-only. A local operator
command can bootstrap only the first admin, with audit and session revocation;
there is no HTTP bootstrap or generic role-grant API. Migrate through 0019 first.
See [the contract and future plans](../docs/manual-seller-review.md) and
[synthetic examples](examples/admin-review/README.md). Documents, verification
standards, additional admins/recovery, appeals, revocation and the admin UI remain
deferred. Approval is administrative access review, not identity/quality certification.

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
