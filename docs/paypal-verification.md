# Credentialed PayPal sandbox verification

This opt-in check exercises the real sandbox adapter and FairMade API using
synthetic seller/buyer fixtures in an isolated, retained SQLite database. The
buyer must approve the transaction in PayPal's sandbox browser flow. It never
uses a fake payment gateway, live PayPal host or actual funds. It does not
establish that the separate frontend SDK/browser integration is working.

## Current status

On 2026-11-11, none of the five sandbox settings was configured in the agent's
process, user/machine environments or standard project-local environment files.
No credentialed PayPal request, approval, capture or refund has been verified.
Offline adapter/refund tests and approval-link checks are separate evidence;
their passing result must not be advertised as a real sandbox transaction.
The targeted offline suite passed 89 tests with the one real-provider case
skipped. Launcher syntax and rejection of live settings before execution passed.
After malformed provider metadata cases were added, the approval-link checks
were rerun separately: twelve passed, with the real-provider case still skipped.

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

The test reports a local .url shortcut under backend/.pytest_cache/paypal-sandbox.
Open that file and approve with the separate sandbox buyer within ten minutes.
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
