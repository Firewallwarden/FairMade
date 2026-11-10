# Frontend completion checklist

## Implemented and locally checked

- Existing cream/sage botanical landing page and clearly labeled signup preview.
- Cost calculator at `/#/pricing`, linked from desktop and mobile navigation.
- Batch costs, labor, usable yield, modeled fees, target margins and optional price scenario.
- Typed, runtime-validated calls to the existing stateless `/api/v1/pricing/analyze` endpoint.
- Backend estimates, cost breakdown, warnings, assumptions and scenario profit/margin.
- Network/validation/error/loading states; inputs are not persisted in browser storage.
- Local Vite `/api` proxy to `http://127.0.0.1:8000`. Production hosting needs an approved API routing configuration.
- Build, lint and eight service/contract tests passed.
- Chrome checks passed for result rendering with a temporary synthetic HTTP response,
  unavailable-backend errors, invalid target margins, stale-result clearing, labor
  add/remove, skip-link focus and a 390px layout without horizontal overflow.
- The temporary response server was stopped. Live backend calculations and actual
  sandbox payments remain unverified: no backend service was running and the
  discovered Python installation did not have FastAPI installed.

## Next — demo contract accepted on 2026-11-09

- Real registration/login/logout, in-memory bearer sessions and seller-application status.
- Seller product management and saved analyses; Quality Lock and evidence-based reviews.
- Explicit Passport disclosure preview/approval and listing publication/stock.
- Live marketplace/search/filtering, listing detail and expandable public Passport.
- Buyer order creation and sandbox SDK approval, backend capture verification and recovery.
- Seller order views, comparisons, secondary capabilities and end-to-end polish.

## Integration decisions and dependencies

The frontend owner accepted the existing demo API shapes on 2026-11-09. The shared
API contract records that bounded acceptance; live/browser verification remains
separate. No backend endpoint or payload changes are proposed.

Accepted browser session default: memory only, fixed backend expiry, no refresh and
no persistent login. Reloading requires signing in again. Seller access continues to
require manual administrator approval. A separate local administrator must be
provisioned through the documented operator process; the frontend must not bypass it.

### Accepted decision for the next milestone

Accept the currently implemented account/session, seller-application, product,
saved-analysis, Quality Lock, comparison/review, Passport, listing, inventory,
order and sandbox-payment shapes for the local demo. Use memory-only browser
sessions and preserve all server authorization, revision and publication approvals.
This does not certify successful browser integration or authorize API changes.

Authorized shared-document edits are limited to `docs/api-contract.md` (record this
frontend acceptance while keeping runtime verification pending) and
`docs/local-mvp-decisions.md` (record the chosen designs, browser session default
and actual frontend verification limits). Approval was given on 2026-11-09.

Server-side PayPal sandbox setup and a credentialed sandbox browser test remain
required. Never interpret SDK approval as verified payment. The backend provides
deterministic explanations and manually supplied evidence, not a connected LLM or
automatic supplier/market price lookup.

The newer recipe, material, completed-production and livestock backend APIs were
found on synchronized main. They are secondary to the authorized seller-to-buyer demo.

## Run locally

From `frontend/`: `npm.cmd run dev`, then open the Vite URL and select **Cost calculator**.
Start the backend using its README; its default port is 8000. No backend database
changes are required by this calculator. An unavailable backend produces an explicit
error, never fabricated results. Optional `VITE_API_BASE_URL` replaces `/api/v1` and
must include that API prefix. Do not put secrets in any `VITE_` variable.

Checks: `npm.cmd run build`, `npm.cmd run lint`, `npm.cmd test`.
The tests use Node's native TypeScript support (Node 22.18+ or a newer supported release).
