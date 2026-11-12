# Credentialed PayPal sandbox verification

This opt-in check exercises the real sandbox adapter and FairMade API using
synthetic seller/buyer fixtures in an isolated, retained SQLite database. The
buyer must approve the transaction in PayPal's sandbox browser flow. It never
uses a fake payment gateway, live PayPal host or actual funds. It does not
establish that the separate frontend SDK/browser integration is working.

## Current status

On 2026-11-11, credentials were configured in a local file outside Git and the
buyer approved a USD 34.00 sandbox order. Real backend capture and the
seller-approved full refund were verified, together with capture/refund retry
safety, inventory settlement once and no automatic restocking on refund.

The original test run stopped on a provider read timeout during approval polling.
PayPal subsequently reported that same order as APPROVED, despite the checkout
page displaying a spinner. Recovery reopened the retained database, logged into
its existing synthetic accounts, and exercised the normal FairMade capture and
refund APIs against that original provider order. It created no replacement order
and bypassed no payment, ownership, expiry or verification rules. The local
recovery report is retained at
`backend/.pytest_cache/paypal-sandbox/run-20261111-224418/resume-result.json`.
This is successful backend recovery evidence, not an uninterrupted pytest pass
or proof of the separate frontend SDK/browser integration.

The verifier now overrides the shared offline fixture only inside its explicitly
opted-in module; ordinary tests still disable real PayPal. Approval polling
retries read-only provider failures within the original ten-minute deadline.
An unexpected order state or unconfirmed approval stops the check and retains
history. Offline adapter/refund tests remain separate evidence and do not
substitute for a credentialed sandbox transaction.

After these verifier fixes, the offline payment/refund suite passed 98 tests
with the opt-in provider case skipped. Ruff lint and formatting checks passed
for the three changed test/helper modules. No additional transaction was created
to obtain these regression results.

## Completed browser checkout check

Later on 2026-11-11 (America/Chicago), the user completed a separate USD 34.00
purchase through FairMade's actual marketplace and PayPal SDK button. The user
confirmed that checkout returned to FairMade and displayed the payment-confirmed
page with paid status. A read-only inspection of the retained database independently
confirmed a completed capture with a nonempty capture ID and verification time,
paid order status through the application's normal status projection, and stock
decreasing from 8 to 6 for two purchased units. The earlier verification order
remains refunded; the new browser-demo order remains paid.

Tested revisions were backend `f4dd89f8862cfd2467f085c8966ed9bb889ce198` and
frontend `feature/frontend-demo` at `1a7f8eab534a1b4197d33061eb39edebd068c51d`.
The existing frontend source was unchanged and its TypeScript/production build
passed using Node 22.23.5. This manual browser acceptance is separate from the
offline suite and the interrupted-and-recovered backend test. It does not claim
that the frontend branch has been integrated into main, that every browser or
failure scenario was tested, or that live payments are supported.

The local, credential-free record summary is retained in the
`FairMade-checkout-browser` verification worktree at
`backend/.pytest_cache/checkout-browser/browser-backend-result.json`.

### Use this flow for the demonstration

1. Start the actual backend on loopback port 8000 with the five sandbox settings
   below loaded into its process. The pytest launcher does not configure a
   separately running API server.
2. Start the accepted frontend with its supported Node runtime. The tested Vite
   server was at `http://127.0.0.1:5173`, proxying `/api` to port 8000. No PayPal
   secret belongs in Vite configuration.
3. Sign in to FairMade as the test buyer, open a published marketplace product,
   review its subtotal and reserve stock. Use the PayPal button on the saved
   FairMade order page; approve with the separate personal sandbox account.
4. Confirm return to FairMade and the backend-verified paid receipt. If status is
   uncertain, inspect/reconcile that saved order before another purchase.

The earlier standalone `.url` handoff bypassed the JavaScript SDK completion
callback and its order had no configured redirect return URL. That handoff is
only a backend approval aid; it is not the browser demo checkout. PayPal could
record APPROVED while that standalone page continued spinning. The complete SDK
flow returned successfully without changing frontend code. Do not use the raw
approval shortcut for the demo or treat approval alone as payment completion.
PayPal documents the SDK callback and backend capture in its
[standard checkout flow](https://developer.paypal.com/studio/checkout/standard/integrate).

## Local configuration

Use a PayPal sandbox business account/REST app and a separate personal sandbox
buyer. Put only these five lines in a local file excluded from Git, replacing
the placeholders locally. Do not paste values into chat or PRs:

```dotenv
FAIRMADE_PAYPAL_ENABLED=true
FAIRMADE_PAYPAL_ENVIRONMENT=sandbox
FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID=REPLACE_LOCALLY
FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET=REPLACE_LOCALLY
FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID=REPLACE_WITH_13_CHARACTER_ID
```

The launcher reads literal NAME=VALUE entries, accepts these five names only,
does not evaluate shell code or expand values, rejects live mode before Python
or networking, and restores its process settings on exit. It does not change
the application's existing rule that .env files are not auto-loaded.

From this checkout, run PowerShell using the configured backend SDK executable:

```powershell
./scripts/Invoke-PayPalSandboxVerification.ps1 `
    -SettingsFile 'C:\path\to\local\sandbox.env' `
    -PythonExecutable 'C:\path\to\configured\python.exe'
```

For backend-only verification, the test reports a local .url shortcut under
backend/.pytest_cache/paypal-sandbox. Open that file and approve with the separate
sandbox buyer within ten minutes. The standalone page is not a browser completion
check; use the SDK flow above for the demo.
Only the provider-returned HTTPS sandbox checkout link for the matching order
is accepted. Neither credentials nor the URL are printed in test output. Never
commit that local file or display account credentials in the demo video.

The backend then captures and verifies the payment. It checks the paid order,
stock settlement exactly once, safe capture retries, a buyer refund request
that leaves the order paid until seller approval, provider-confirmed refund,
safe refund retries and no automatic restocking. Refund-pending results receive
bounded read-only reconciliation; unresolved results fail and retain history.

## Scope and recovery

The fixture order is USD 34.00 for two units of a synthetic product. Its database
and approval shortcut are retained under the ignored cache folder; there is no
automatic deletion. Preserve that directory when a result is uncertain and
reconcile the original order instead of creating repeated charges to force a
pass. Check sandbox transaction history before another run. Only sandbox
payments are in scope; no production merchant or application role policy changes.

The test uses existing synthetic, preverified seller fixtures in its isolated
database. Normal manual seller approval remains unchanged. The real browser
frontend journey, including SDK callbacks and UI receipt display, remains a
separate frontend integration check.

Provider behavior follows the official
[Orders v2](https://developer.paypal.com/api/orders/v2) and
[Payments v2](https://developer.paypal.com/api/payments/v2) APIs. Existing
[sandbox setup and recovery](../backend/examples/paypal/README.md) and
[refund workflow](../backend/examples/refunds/README.md) cover application behavior.
