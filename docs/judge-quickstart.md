# Run and evaluate FairMade

FairMade is a functional local Windows desktop-browser prototype. This guide uses
the existing runtime scripts; no hosted account or paid cloud AI is needed.
Internet access is needed to install dependencies/models and use PayPal sandbox.
The first model download is substantial. No application credentials or private
merchant secrets are bundled.

## 1. Install and start

Install Git for Windows, Node.js 22.18+ supported by Vite 8, Python 3.11+ with
venv/pip, and Windows PowerShell. See the [complete dependency guide](local-development.md#1-install-the-dependencies)
for versions and installation links. GitHub CLI is contributor tooling, not needed
for the judge's runtime path below.

In PowerShell, clone the repository into a directory you own:

```powershell
git clone https://github.com/Firewallwarden/FairMade.git
Set-Location .\FairMade
$repo = (Get-Location).Path
$runtime = Join-Path $env:LOCALAPPDATA 'FairMade\runtime'
$judgePython = (py -3 -c 'import sys; print(sys.executable)').Trim()
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Initialize-LocalRuntime.ps1" `
  -Repository $repo -RuntimeRoot $runtime -PythonExecutable $judgePython
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Start -RuntimeRoot $runtime
Invoke-RestMethod 'http://127.0.0.1:8000/health'
```

If the Python launcher is unavailable, set `$judgePython` to the full path of
your installed Python executable. Initialization installs dependencies, exports
committed main into a directory outside the checkout, and migrates a local SQLite
database. It does not populate accounts or publish products. It is intentionally
not a reset command; preserve existing local records on subsequent runs.

Open http://127.0.0.1:5173/ for the app and http://127.0.0.1:8000/docs for
interactive API documentation. Keep ports 5173 and 8000 free. Troubleshooting and
logs are documented in the [full guide](local-development.md#troubleshooting).

## 2. Enable the two hackathon integrations

**AI:** install Ollama 0.24.0, start its loopback service, and run
`ollama pull qwen3:8b`. In the generated private file
`$runtime\private\settings.json`, change `FAIRMADE_ASSISTANTS_ENABLED` to the
string `"true"`. Follow [AI setup](local-development.md#6-enable-local-ai-and-receipt-ocr).
Tesseract with English data and the receipt settings are required only for scanning
receipts. Regular cost calculations do not need the model.

**PayPal:** create your own free sandbox Business merchant, REST app and separate
sandbox Personal buyer. Follow [sandbox configuration](local-development.md#7-configure-paypal-sandbox-on-each-developer-machine)
to enter the client ID, secret and merchant ID into that private settings file.
Use Sandbox, not Live. These values stay outside the checkout; no special access
to the developers' merchant is required. Without them checkout remains disabled.

After saving settings, restart:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Stop -RuntimeRoot $runtime
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Start -RuntimeRoot $runtime
Invoke-RestMethod 'http://127.0.0.1:5173/api/v1/paypal/config'
```

The last response should report enabled sandbox checkout. Never paste secrets
into browser variables or include them in a bug report.

## 3. Create accounts and approve a synthetic seller

1. Register three separate synthetic FairMade accounts: reviewer, seller applicant
   and buyer. Use local test passwords of your own. Everyone starts as a buyer.
2. Sign in as the seller applicant and submit the seller application.
3. Sign in as reviewer and obtain its account UUID from `GET /api/v1/auth/me` in
   the interactive API docs using that account's login token. The auth endpoints
   and request fields are shown there. Keep the token private.
4. In a separate PowerShell terminal, point the existing first-admin command at
   the same runtime database and reviewer UUID:

   ```powershell
   $runtime = Join-Path $env:LOCALAPPDATA 'FairMade\runtime'
   $judgeSettings = Get-Content "$runtime\private\settings.json" -Raw | ConvertFrom-Json
   $env:FAIRMADE_DATABASE_URL = $judgeSettings.FAIRMADE_DATABASE_URL
   $reviewerId = Read-Host 'Reviewer account UUID'
   & "$runtime\venv\Scripts\python.exe" -m fairmade.admin_bootstrap `
     --account-id $reviewerId --reason 'Synthetic local judge reviewer setup'
   Remove-Item Env:FAIRMADE_DATABASE_URL
   ```

5. Log out and back in as reviewer because bootstrap revokes previous sessions.
   Open administrator seller-application review, inspect the separate applicant
   and approve it with a synthetic review reason. You cannot approve yourself.
6. Sign in as seller. Seller workspace should now be available. This is access
   review, not certification of identity or product quality. See the
   [review contract](manual-seller-review.md) and [operator example](../backend/examples/admin-review/README.md).

There are no shared hardcoded judge credentials. Creating local accounts gives
judges their own isolated data. A new database's marketplace starts empty; the
homepage's labeled illustration cards are not live listings.

## 4. Walk through the working product

1. **Seller:** create a synthetic sourdough or egg product, record production
   inputs and run a saved cost analysis. The anonymous Pricing calculator is also
   available for a quick deterministic calculation before seller setup.
2. **Quality:** add a mandatory Quality Lock and supplier evidence. Compare
   alternatives and inspect an excluded quote. Clearly mark these as synthetic
   seller-reported inputs, not verified local supplier offers.
3. **AI:** from the product's seller assistant, select the saved analysis and ask
   it to explain the costs or a proposed-price scenario. Inspect the exact facts
   separately from the qualitative answer; try a follow-up.
4. **Publish:** create a Passport draft, choose disclosures, generate a fresh
   preview and explicitly approve publication. Supply stock/listing availability
   through the seller controls. Private recipe data is not public by default.
5. **Buyer:** use a separate browser session, sign in as the buyer, open The market,
   inspect the approved listing/Passport and ask the buyer assistant why it costs
   what it does. Browser login state is memory-only; sign in again after reload.
6. **PayPal:** reserve a purchase, approve it using your separate sandbox Personal
   account through the in-app PayPal flow, then return to FairMade. Confirm the
   order is paid only after backend capture verification; inspect updated stock
   and order history. Do not buy your own listing or use real payment information.
7. **After purchase:** inspect order messages and pickup/history. Refund requests
   require seller review and provider confirmation; never fabricate paid or
   refunded records to populate a demonstration.

The [frontend feature map](../frontend/README.md#where-to-find-features) gives
navigation details. The [API contract](api-contract.md) and generated API docs
describe required fields. Current evidence and known skips live in the
[browser acceptance record](../frontend/e2e/ACCEPTANCE.md),
[PayPal verification](paypal-verification.md) and
[receipt verification](receipt-verification.md). This document does not claim a
new clean-machine or end-to-end test was executed by the submission-docs chat.

## Stop or resume

Use the Stop command above to stop only the managed app processes. Data and
settings persist. Resume with Start. Ollama runs separately. For updated code,
follow the [refresh procedure](local-development.md#10-refresh-the-shared-demo-after-integration)
and preserve a database backup before migrations.
