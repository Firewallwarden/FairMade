# Browser workflow suite

Run from this feature's `frontend` directory, outside the primary main checkout:

```powershell
npm.cmd ci
npx.cmd playwright install chromium
npm.cmd run test:e2e:check
npm.cmd run test:e2e
```

`E2E_PYTHON` can select an existing Python environment with the backend dependencies
installed. On Windows it defaults to the central local runtime environment; on
other systems it defaults to `python3`. `E2E_API_PORT` and `E2E_WEB_PORT` default
to 8002 and 5174. Occupied ports fail rather than reusing an unknown service.

The runner migrates a **fresh isolated SQLite database** below
`frontend/.e2e/<run-id>/`, creates synthetic accounts with a random per-run password,
and uses the existing first-administrator operator command. A real browser approves
the synthetic seller and denies another application. No backend implementation is
modified and no retained demo database is used. API calls prepare source fixtures;
workflow assertions use the real website and backend. Successful payments,
extracted receipts and model answers are never fabricated.

Projects exercise desktop Chromium and narrow-screen Chromium with iPhone 13
viewport/touch settings. This is not a claim of Safari/WebKit coverage. The suite
uses accessible labels, roles and keyboard actions; it is not a full accessibility
audit. Run results and HTML reports are retained under each ignored run directory.

## Workflow coverage

| Area | Browser workflows |
| --- | --- |
| Accounts | Registration, buyer defaults, seller application, logout, revoked session, signed-out and role boundaries |
| Administrator | Queue/detail, approval, denial, stale revision reload; decisions run against the actual backend |
| Products/economics | Product creation/editing, saved deterministic analysis, historical selection |
| Recipes/production | Recipe save/edit, saved costing, completed report, reopening, animal/group attribution |
| Quality | Mandatory rule, failed candidate, stored claims/rules/checks, changed-requirement warning |
| Comparisons/sourcing | Dated observations, saved comparison, source details, supplier quotes, mandatory exclusions, recommendations |
| Supplier records | Private profile creation/edit, reported experience, reliability and reopening |
| Materials/livestock | Receipt/usage movements and balances, metadata/history, group/animal creation/edit, attribution |
| Publication | Disclosure choices, saved draft editing, revision conflict/reload, fresh preview, explicit Passport/listing approval, withdrawal |
| Discovery | Marketplace filters, radius POST and returned distances, public comparison, favorites |
| Planning/preferences | Explicit preference consent/disable, suggestions, basket optimization, purchase preview, buyer/seller pair suggestions |
| Orders | Reservation, participant messaging, seller cancellation, fresh inventory availability, refund-list empty states, pickup-history empty state |
| History pagination | Older analyses, retained multiple quality selections, older sourcing detail, quote selection across pages |
| Assistants | Saved conversation, transport failure/retry identity, disabled-provider messaging, deletion and revoked access; real-model continuity is opt-in below |
| Reports | Insights, forecasts, calendar, pricing advice, aggregate and itemized sales, date changes and unknown coverage |

The matrix describes implemented scenarios. It does not turn skipped provider
cases into completed acceptance. Positive paid-order, populated refund/pickup and
receipt extraction/approval cases require the provider setup below.

## Real local model

Start the existing Ollama service with the installed `qwen3:8b` model. Then:

```powershell
$env:E2E_PROVIDERS = '1'
npx.cmd playwright test assistant-workflows provider-workflows --project=desktop
Remove-Item Env:E2E_PROVIDERS
```

The buyer and seller tests ask a referential follow-up, navigate away and reopen
saved history. Seller context explicitly selects its saved analysis/review. The
buyer also checks that withdrawn source access is reported. The separate memory
workflow enables consent first, proposes preferences from an explicit question,
and verifies that only a separately reviewed save updates the active profile.
Run it with `npx.cmd playwright test memory-workflow --project=desktop` and
`E2E_PROVIDERS=1`. The backend currently recognizes explicit budgets written
as `USD 8` or `$8`; suffix notation such as `8 USD` can be rejected. Description generation separately exercises
private review/edit/approval. Provider cases allow longer timeouts; no model/cloud
fallback or auto-retry hides a failed inference. Keep configuration and source
files unchanged during a run: Vite restarts clear the app's in-memory session.

## Receipt fixture

Set `E2E_PROVIDERS=1`, `E2E_RECEIPT_IMAGE` to a private real receipt PNG/JPEG, and
`E2E_RECEIPT_REVIEW` to a private JSON file containing the reviewed ground-truth
values. Its shape is the documented `ExpenseDetails`: merchant, purchased_on,
currency, category, subtotal, tax, total and items (description, line_total).
Unknown optional amounts use null; do not invent values to satisfy approval.
Tesseract with English data must be installed; `FAIRMADE_TESSERACT_PATH` can select
its executable. The test uploads, inspects the draft, applies reviewed corrections,
approves the saved preview and finds the resulting expense. The receipt and
reviewed JSON are not committed. Provider screenshots/traces are disabled.

## PayPal sandbox and refunds

Set `E2E_PAYPAL=1` and the existing server-only sandbox settings:
`FAIRMADE_PAYPAL_ENABLED=true`, `FAIRMADE_PAYPAL_ENVIRONMENT=sandbox`,
`FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID`, `FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET`, and
`FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID`. Supply a separate sandbox personal buyer
through private `E2E_PAYPAL_BUYER_EMAIL` and `E2E_PAYPAL_BUYER_PASSWORD` variables.
Use the process environment or your private settings mechanism, never `VITE_`
variables or committed credential files.

The provider tests complete sandbox approval through the website and wait for
backend-verified capture. They also create/edit/withdraw an eligible purchase review, exercise pickup changes/history and buyer refund
requests with populated buyer/seller inbox links and seller approval/denial. The approval case drops the browser response
**after the real backend request** to exercise refresh/reconciliation; it does not
manufacture a refund status. External PayPal UI changes, MFA or anti-bot challenges
may require supervised acceptance. Never substitute a live PayPal account.

## Evidence and source identity

```powershell
node e2e/endpoint-coverage.mjs
# Or pass a particular run UUID as the final argument.
```

The ignored endpoint report counts observed browser responses only, excluding API
fixture seeding. It retains method, sanitized path template and status; no queries,
bearer tokens, request bodies, receipt contents or answers. Counts demonstrate
observed coverage, not every permission/state combination. Inspect skipped/failed
cases in the corresponding HTML report before calling acceptance complete.

The HTML contains `fairmade-source-revision` and `fairmade-source-state` metadata.
The setup project checks the served revision against the checkout under test.
After committing/pushing a review build, restart the server and verify the metadata
matches the published head and says `clean`. An exported runtime snapshot can set
`FAIRMADE_SOURCE_REVISION` to its exact 40-character source commit. An unidentified
export says `unknown`, never silently claims the latest main.
