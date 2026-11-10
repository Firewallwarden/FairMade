# Frontend completion checklist

## Complete for the accepted local demo slice

- Cream/sage botanical design and a guided create/calculate/review/publish journey.
- Real registration/login/logout, fixed-expiry memory-only sessions and seller applications.
- Private product creation/editing, saved analyses, cost breakdowns, break-even,
  target margins and scenarios, calculated by the backend.
- Boolean/choice/numeric Quality Locks, candidate claim checks and failure warnings.
- Manually sourced/dated price observations, normalized comparison reports and
  optional review/Passport context, including stale/incompatible evidence.
- Opt-in disclosures, exact Passport/listing preview/hash approvals and stock entry.
  Editing inputs clears stale previews.
- Marketplace search/type/location/availability filters, pagination and product details.
- Summary-first expandable Passports; raw private inputs are not exposed.
- Single-product subtotal preview, idempotent stock reservation, buyer/seller order
  views, cancellation and stock release.
- Sandbox SDK wiring, backend capture/reconciliation, uncertain-payment messaging
  and verified receipt gating. Actual PayPal approval/capture is not yet verified.
- Runtime response decoding, request timeouts, loading/empty/error states and
  keyboard/mobile handling. No new runtime dependencies or production mocks.

## Checks actually performed

- Production build (including TypeScript), Oxlint and 14 frontend tests passed.
- 460 targeted backend tests passed: pricing, seller data, Quality Locks, Passports,
  marketplace, orders, payment verification and comparisons. Payment tests use
  provider doubles, not real PayPal. Existing Starlette/httpx and Pydantic warnings
  remain in the backend test environment.
- Chrome exercised real FastAPI against an isolated migrated SQLite database:
  registration/login/logout, pending seller access, documented administrator approval
  and account refresh, product creation, saved pricing, a failed Quality Lock,
  inventory, explicit Passport/listing approval, browsing/search/empty results,
  public privacy, USD 16.00 order reservation, disabled-checkout messaging,
  cancellation and release of stock.
- Chrome also saved sourced observations and a comparison report, included its
  quantity/range in a Passport draft, and verified editing clears the preview.
- Initial synthetic-response rendering tests preceded these real backend checks.
  The temporary fixture server was stopped. Only homepage inspiration cards remain
  illustrative, visibly labeled and excluded from checkout.
- Responsive/keyboard checks include a 390px layout, skip links and form controls;
  this is not a full accessibility audit.

## Genuine blocker

PayPal is disabled on the local backend. Its owner must configure the server-only
variables in [backend/.env.example](../backend/.env.example) and restart the API:
`FAIRMADE_PAYPAL_ENABLED=true`, `FAIRMADE_PAYPAL_ENVIRONMENT=sandbox`,
`FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID`, `FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET`,
and `FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID`. Never put private credentials in
frontend code or `VITE_` variables.

Then test SDK approval, backend-verified capture, receipt, cancellation, provider
failure/timeout and reconciliation with a sandbox buyer. The purchase workflow is
not complete until that credentialed browser test passes.

## Remaining outside this slice

- Supplier sourcing/savings, photo upload management, storefront/nearby discovery,
  favorites, refunds, pickup progress, profitability and product reviews have
  backend capabilities; their full frontend and still-proposed contracts need
  subsequent slices. Existing published photos display; their selections are
  preserved during listing edits.
- Newer recipe/material/production/livestock tools are outside the priority demo UI.
- No LLM or automatic external price lookup is connected. Explanations are
  deterministic and labeled. Future AI integration needs an agreed API/provider;
  no missing endpoint is assumed to exist.
- Reload intentionally loses memory-only login and any reservation retry key.
  After an uncertain request, check Orders before starting another reservation.
  The current page retains its key and blocks edits while an outcome is uncertain.
- Production security/hosting, real payments/payouts, shipping and tax are deferred.

## Decisions and ownership

The frontend owner accepted the existing account/session, seller-application,
product, saved-analysis, Quality Lock, comparison/review, Passport, listing,
inventory, order and sandbox-payment contracts on 2026-11-09, together with
memory-only sessions and edits to the shared API contract and MVP decisions.
No backend source, endpoint or payload was changed. Tests used a dedicated
synthetic reviewer/applicant in the isolated demo database, preserving manual
seller approval and self-purchase restrictions.

## Run and review

Worktree: `feature/frontend-demo`. From its `frontend/`, run `npm.cmd run dev`;
start FastAPI on port 8000 per the backend README. Vite proxies `/api`.
Optional `VITE_API_BASE_URL` replaces `/api/v1` and must include that prefix.
Production hosting needs approved API routing; the development proxy is not bundled.

Checks: `npm.cmd run build`, `npm.cmd run lint`, `npm.cmd test`.
Tests require Node 22.18+ native TypeScript support. Use separate buyer/seller
accounts. No changes have been pushed or deployed.
