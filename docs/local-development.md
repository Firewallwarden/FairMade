# Local development and test environment (Windows)

This guide separates source checkouts from running services, dependencies and
private test data. Open the primary `FairMade` checkout in WebStorm for reference.
Keep `main` clean; implement changes in a dedicated feature worktree. Run the
shared local demo from `%LOCALAPPDATA%\FairMade\runtime`, outside every checkout.

The scripts in this guide are Windows PowerShell scripts. They use the checked-in
frontend lockfile and backend requirements; they do not add a database service,
paid API, cloud AI provider or production deployment.

## 1. Install the dependencies

| Dependency | Purpose and required setup |
| --- | --- |
| Git for Windows | Clone, fetch, worktrees and revision snapshots. |
| GitHub CLI (`gh`) | Feature publication and the checked-in PR readiness guard. Authenticate locally with `gh auth login`. |
| Node.js and npm | Frontend Vite/React/TypeScript tooling. Native TypeScript tests require Node **22.18+**; use a Node release supported by the lockfile's Vite version. This machine's current tested runtime is Node 26.13.0. |
| Python **3.11+** with `venv` and pip | Backend and tests. This machine's centralized environment uses Python **3.14.5**. Use an explicit executable path if `python` opens the Microsoft Store alias. |
| **Ollama 0.24.0** | User-confirmed backend development baseline. Install it locally and keep its service on loopback. Needed for AI conversations, description drafts and receipt extraction; ordinary pricing and catalog operations do not require it. |
| Ollama model **`qwen3:8b`** | Exact model name hardcoded by the existing backend gateway. A different tag is not an interchangeable configuration setting. |
| Tesseract OCR with **English (`eng`) language data** | Receipt-image extraction. This machine has Tesseract **5.5.3.20260724** at `C:\Program Files\Tesseract-OCR\tesseract.exe`. |
| PayPal Developer sandbox accounts and REST app | Needed only for real sandbox checkout. Credentials must be configured separately on **each machine**, outside Git. |

Use the official [Git](https://git-scm.com/downloads/win),
[Node](https://nodejs.org/en/download), [Python](https://www.python.org/downloads/windows/),
[GitHub CLI](https://cli.github.com/), [Ollama](https://ollama.com/download/windows),
and [Tesseract installation guidance](https://tesseract-ocr.github.io/tessdoc/Installation.html).
For this project's current baseline, select Ollama 0.24.0 rather than assuming
that whichever version is newest has been evaluated. Installers are separate
from Python/npm packages and may require interactive Windows installation.

The complete package requirements live in
[`frontend/package.json`](../frontend/package.json), the committed
[`package-lock.json`](../frontend/package-lock.json), and
[`backend/pyproject.toml`](../backend/pyproject.toml). Do not install them globally:

- Frontend runtime: React and React DOM. Development/build: TypeScript, Vite,
  React's Vite plugin, Tailwind and its Vite plugin, React/Node type packages,
  and Oxlint. `npm ci` installs the locked direct and transitive packages.
- Backend runtime: FastAPI, Pydantic with email validation, Uvicorn, SQLAlchemy,
  Alembic, Argon2 password hashing, HTTPX and Pillow. The `dev` extra adds pytest
  and Ruff. The initializer installs all required transitive packages in its
  virtual environment. Backend ranges are declared requirements, not a fully
  pinned lockfile; validate a fresh environment with the documented checks.
- Ollama, the Qwen model, Tesseract/English data and PayPal accounts/credentials
  remain separate prerequisites; pip and npm do not install or configure them.

Use a current supported browser for manual UI testing. The optional agent browser
automation CLI is test tooling, not a requirement to run FairMade normally.

Verify in a **new** PowerShell terminal after installation:

```powershell
git --version
gh --version
node --version
npm.cmd --version
py --list
ollama --version
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --version
& 'C:\Program Files\Tesseract-OCR\tesseract.exe' --list-langs
```

Confirm `eng` appears. `osd` alone is insufficient. Tesseract does not provide an
AI model and has no role in PayPal authentication or payment verification.

## 2. Obtain a clean source checkout

For a new machine:

```powershell
git clone https://github.com/Firewallwarden/FairMade.git
Set-Location .\FairMade
```

For an existing primary checkout, first preserve any edits, then run:

```powershell
$repo = 'C:\Users\YOUR_NAME\WebstormProjects\FairMade'
Set-Location $repo
git status --short
git fetch origin
git pull --ff-only
```

Read root `AGENTS.md` and the specialist instructions. The primary worktree is for
reference and fast-forward maintenance, not feature development or test execution.
Do not reuse a retired feature branch as the main checkout. Open `$repo` with
**File > Open** in WebStorm and start future agent chats in that project.
An existing chat's host process can retain its old working directory; opening a
file in another project does not transfer that chat automatically.

## 3. Initialize the central runtime

```powershell
$runtime = Join-Path $env:LOCALAPPDATA 'FairMade\runtime'
$python = 'C:\Users\YOUR_NAME\AppData\Local\Programs\Python\Python314\python.exe'
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Initialize-LocalRuntime.ps1" `
  -Repository $repo -RuntimeRoot $runtime -PythonExecutable $python
```

Use the actual Python path on your machine. The process-scoped execution-policy
argument permits this reviewed local script; it does not change machine policy.

Initialization exports committed `origin/main` with `git archive` into an immutable
revision directory. It installs frontend packages with `npm ci` from the lockfile,
creates a separate Python virtual environment, installs `backend[dev]`, and runs
Alembic to the current migration head against the central SQLite file. It creates
a private settings template only if one does not already exist. It does not fetch
Git changes, reset data, create users, approve sellers, seed listings or make payments.
Stop the managed runtime before changing its revision.

```text
%LOCALAPPDATA%\FairMade\runtime\
  releases\<git-commit>\      source snapshot; no .git directory
  dependencies\frontend\    npm manifest, lockfile and shared node_modules
  venv\                     Python environment; no checkout dependency
  data\fairmade.sqlite3     persistent local application records and photos
  private\settings.json    server-only settings; access restricted to user/System
  logs\                    backend/frontend output; inspect locally
  current.json              selected revision, source checkout and release path
  processes.json            owned PIDs, executable paths and creation times
```

The scripts are usable from the source checkout without running a service there.
They may also be copied to `$runtime\bin` for a stable management location; always
pass `-Repository $repo` to the initializer when using that copy. Do not edit release
files to develop features: changes there are not tracked and are not refreshed
from an uncommitted worktree. `-Revision` can explicitly select a committed feature
revision for local testing. Stop, select it deliberately, then return to `origin/main`
when finished. `-SkipDependencyInstall` is only for an already prepared environment;
it is not a fresh-machine shortcut.

## 4. Configure private settings locally

Open the generated file locally:

```powershell
notepad.exe "$runtime\private\settings.json"
```

Keep its existing absolute `FAIRMADE_DATABASE_URL`. Relative SQLite paths are
resolved against the backend working directory and can accidentally create an
empty database if copied between folders. Never point automated tests at your
retained demo database. Local SQLite also stores private photos and business
records: retain a consistent backup before cleanup or migration.

All values in this JSON file must be strings. The manager loads these settings
only into the backend process, then restores its own environment before launching
Vite. FastAPI does **not** automatically read `.env` or this JSON file when started
manually. Changes to settings require a backend restart.

Do not commit this file, passwords, bearer tokens, sandbox credentials or actual
payment information. Runtime files are outside Git by design; there is no reason
to add them with `git add -f`. If credentials are ever exposed, rotate them through
the provider rather than merely removing the visible text.

## 5. Start, stop and check the services

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Start
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Status

Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:5173/api/v1/paypal/config'
```

Open [the frontend](http://127.0.0.1:5173/) and
[interactive API docs](http://127.0.0.1:8000/docs). The frontend proxies `/api`
to port 8000; exact CORS origins are only needed when intentionally using a
separate browser API origin. Do not solve a connection problem with wildcard CORS.

To stop:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File "$repo\scripts\Manage-LocalRuntime.ps1" -Action Stop
```

The manager validates owned PID identity before stopping its services. It refuses
to kill an unknown process occupying 5173 or 8000. Stopping does not erase the
database, private settings, source snapshots or installed dependencies. Ollama is
a separate locally installed service; do not stop it merely to restart Vite.

## 6. Enable local AI and receipt OCR

Finish installing **Ollama 0.24.0**, open a new terminal, and check:

```powershell
ollama --version
ollama list
Invoke-RestMethod 'http://127.0.0.1:11434/api/version'
```

If Ollama is not already serving, start it with the installed Windows application
or `ollama serve` from its installed location. Do not run duplicate services on
11434. If `qwen3:8b` is missing, obtain it explicitly with `ollama pull qwen3:8b`.
This is a substantial download and needs local disk/RAM capacity; do not infer
that installing the Ollama application also installed the model. Check
`http://127.0.0.1:11434/api/tags` or `ollama list` for the exact tag.

In private `settings.json`, set:

```json
"FAIRMADE_ASSISTANTS_ENABLED": "true",
"FAIRMADE_RECEIPTS_ENABLED": "true",
"FAIRMADE_TESSERACT_PATH": "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
```

These are entries inside the existing JSON object, not a second object appended
to the file. Stop/start the runtime after saving. The existing backend uses
`http://127.0.0.1:11434/api/chat`, `qwen3:8b`, structured responses and no cloud
fallback. Receipt imports need **both** Tesseract and the model gateway; reading
and approving an existing draft does not require OCR to be available.
Use synthetic receipts first. Extraction is a draft; explicit seller review and
approval create the expense. AI/OCR must not silently update production costs,
stock or published disclosures. See [receipt operation and limits](receipt-expenses.md)
and [verified OCR evidence](receipt-verification.md).

## 7. Configure PayPal sandbox on each developer machine

**Real sandbox capture/refund and a separate browser checkout were already
successfully verified by the backend workflow.** That evidence is recorded in
[PayPal verification](paypal-verification.md). A fresh local setup still needs
its own private credentials; an unconfigured instance is not a regression in the
verified implementation. Do not create a new transaction solely to repeat that
historical verification during environment cleanup.

1. Sign in to the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/).
2. Select **Sandbox**, not Live. Use a sandbox **Business** merchant account and
   a REST app belonging to that business account.
3. Obtain that sandbox REST app's **client ID** and **client secret** locally.
   Obtain the same business account's **13-character merchant account ID**; an
   email address, app name or client ID is not the merchant ID.
4. Create/use a separate sandbox **Personal** buyer account. Keep its login outside
   Git as well. Do not use the merchant's account to approve its own checkout.
5. Edit the existing private settings entries locally:

```json
"FAIRMADE_PAYPAL_ENABLED": "true",
"FAIRMADE_PAYPAL_ENVIRONMENT": "sandbox",
"FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID": "REPLACE_LOCALLY",
"FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET": "REPLACE_LOCALLY",
"FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID": "REPLACE_LOCALLY"
```

6. Restart the backend with the manager. The public `/api/v1/paypal/config` response
   should report enabled sandbox checkout. It exposes the public client ID when
   needed by the SDK, never the secret. Do not put the secret in a `VITE_` variable.
7. Sign in to FairMade with a buyer different from the listing's seller. Use an
   approved, active listing with recorded stock, reserve the order, then use the
   PayPal button **inside FairMade** and approve with the sandbox Personal account.
8. Confirm the return to a paid FairMade receipt **after backend-verified capture**.
   Approval, a button click or a standalone provider URL is not a paid order.
   On an uncertain outcome, inspect/reconcile the existing order before retrying
   or creating another reservation. Do not refund or restock automatically.

Internet access to PayPal's sandbox API and JavaScript SDK is required. No live
merchant setup, real funds or production payout integration is needed for this
local shared-merchant sandbox. The existing implementation does not require you
to create a public webhook/tunnel just to use its supported local SDK/capture flow.
See PayPal's [standard checkout prerequisites](https://developer.paypal.com/studio/checkout/standard/getstarted?backend=python)
and [API credentials overview](https://developer.paypal.com/api/get-started/).

## 8. Create synthetic test accounts and seller data

Register separate FairMade buyer and seller-applicant accounts. Registration
defaults to buyer and an application does not grant seller access. Use a third
synthetic reviewer account for the documented administrator review; an account
cannot approve itself. For a brand-new isolated database, the existing first-admin
operator command is documented in
[the administrator setup example](../backend/examples/admin-review/README.md).
Use that command with the **central database environment** and central Python;
do not bypass approval by editing role tables or adding a frontend shortcut.

The optional [twelve-product demo seed](../frontend/scripts/seed-demo-catalog.mjs)
requires an existing approved synthetic `qa-seller-<uuid>@example.com`, explicit
`FAIRMADE_DEMO_SEED=true`, and credentials in the current process. Override its
`FAIRMADE_DEMO_API` to `http://127.0.0.1:8000/api/v1` for this runtime; the older
script defaults to 8001. Inspect its retry-state file before changing API/accounts.
The seed is never run automatically and must not duplicate records in a retained
database. Use the existing migrated demo data when present.

## 9. Develop and run automated checks

Create an independent feature worktree from freshly fetched `origin/main` outside
the main checkout. Read both instruction files there. A frontend worktree can
use a `frontend/node_modules` junction to the central frontend dependency folder
when its lockfile matches; unlink only the junction before deleting that worktree.
Never recursively delete the junction's shared target. If a branch changes the
lockfile, install its dependencies separately rather than mutating the shared
demo environment under a running process.

Run from that feature's `frontend` directory:

```powershell
npm.cmd run build
npm.cmd run lint
npm.cmd test
```

For backend checks, use the central environment executable from the feature root,
with `PYTHONPATH` pointing at **that feature's** backend source:

```powershell
$testPython = "$runtime\venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path (Get-Location) 'backend\src'
& $testPython -m pytest -c backend/pyproject.toml backend/tests
& $testPython -m ruff check backend
& $testPython -m ruff format --check backend
Remove-Item Env:PYTHONPATH
```

Do not load retained-demo settings into the test terminal. Ordinary suites use
isolated databases/provider doubles; real PayPal and model/OCR checks are separate
explicit opt-ins, documented in their verification guides. There are no payment
credentials in the repository. Application test execution on primary `main` is
not part of this workflow.

## 10. Refresh the shared demo after integration

1. Verify the feature merge on fetched `origin/main` with the readiness guard.
2. Stop the managed runtime, and make a SQLite backup before schema changes:

   ```powershell
   $backup = Join-Path $runtime ('data\before-refresh-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.sqlite3')
   & "$runtime\venv\Scripts\python.exe" -c "import sqlite3,sys; source=sqlite3.connect(sys.argv[1]); target=sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()" "$runtime\data\fairmade.sqlite3" $backup
   ```

   Use SQLite's backup operation rather than copying an actively used database
   file and forgetting its journal/WAL. Preserve the resulting backup locally.
3. Fast-forward the clean primary checkout with `git pull --ff-only`.
4. Run `Initialize-LocalRuntime.ps1` again; it selects a new committed snapshot,
   checks the frontend lockfile, installs backend requirements, and migrates the
   same central database. Private settings and data are not reset.
5. Start the runtime and check health, the API proxy, sign-in, marketplace and the
   feature's meaningful failure/permission states.

The previous release directories are retained for diagnosis. Selecting an older
snapshot does **not** reverse database migrations; restore a deliberate compatible
backup rather than pointing old code at a newer database blindly.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `python` opens the Store | Use `py --list` and pass the installed interpreter's full path. |
| PowerShell blocks a script | Run the shown process-scoped command; do not change machine execution policy globally. |
| Frontend loads but API fails | Check `/health`, port 8000, backend logs, and the `/api` proxy. |
| Empty records after moving folders | Check the absolute SQLite URL. Preserve both databases; never delete one merely because it looks empty. |
| Port is occupied | Inspect `Get-NetTCPConnection` and its owning process; stop the known old service, not every Node/Python process. |
| PayPal remains disabled | Edit private settings for this machine and restart; an `.env.example` file does not configure a running server. |
| PayPal OAuth/merchant error | Check sandbox/live pairing, REST app/business-account ownership, secret and the 13-character merchant ID. Do not log values. |
| Seller routes return 403 | Complete the documented manual seller approval and refresh the account; do not change roles in the UI. |
| `ASSISTANT_UNAVAILABLE` | Verify Ollama 0.24.0 is serving on 11434, `qwen3:8b` is present and AI is enabled in the API process. |
| `OCR_UNAVAILABLE` | Check the exact Tesseract executable, `eng` data and receipt limits. Tesseract alone cannot replace Ollama extraction. |
| Worktree removal fails | Check current directories of running servers, node_modules junctions, untracked/ignored local data and open IDE/chat handles. Preserve data before cleanup. |

## Migration evidence for this machine

The 2026-11-12 cleanup took consistent backups of the old 8000 and 8001 SQLite
databases and checked integrity plus all **54** table counts before retiring the
servers. The first becomes `data/fairmade.sqlite3`; the second is retained as
`data/legacy-8001.sqlite3`. The initial central snapshot is main `a1a6119`; later
refreshes use `current.json` as the authority. Settings are private and PayPal
starts disabled until configured locally. Ollama's loopback API now reports
**0.24.0**; `qwen3:8b` was not yet present at this migration check, so AI/receipt
extraction remains disabled until that separate model setup is completed. This
is runtime-migration evidence, separate from prior successful PayPal and OCR
verification.

After PRs #77–#81 integrated, the runtime was refreshed to main `16309c0` and its
frontend build, Oxlint and **43/43 tests** passed. The freshly installed central
Python environment passed **1,623 backend tests**, with **30 skipped** and one
existing dependency warning; no new credentialed payment or model run was made.
The backend source is unchanged between the initial and refreshed main snapshots.
Chrome checked the central landing page, live marketplace and signed-out livestock
access boundary. A complete stop/refresh/start cycle retained private settings and
data; duplicate starts and checkout-local runtime paths were rejected without
replacing running processes or writing into main. Backend test logs/JUnit and
frontend check logs remain under the central `logs` directory, outside Git.
