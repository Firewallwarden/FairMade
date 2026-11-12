# Real receipt verification

This check uses actual Tesseract and local Ollama/Qwen3 over clearly synthetic
receipt images. It does not require uploaded personal receipts, paid inference,
frontend changes or modifications to production business data.

## Current evidence

On 2026-11-11, the existing receipt API/image-validation checks passed: 22 tests
passed, with three opt-in provider cases skipped in that run. The machine had
no Tesseract executable or configured path. Winget reported no applicable
per-user installer; execution policy blocked the automated download/install
action. Installation must be completed locally before full OCR is claimed.

The existing Ollama service was offline and was started using its already
installed executable. The existing qwen3:8b model was present; no model was
downloaded. The separate real text-model extraction check is distinct from
the full image checks. That real text-model extraction check passed after the
service was started (one passed, two image cases deselected).

Full PNG/JPEG OCR verification remains pending installation. A requested real
image run now fails explicitly when its OCR prerequisite is missing, rather
than reporting success with the image checks silently skipped.

## Run the full check

Install Tesseract with English language data using the
[upstream installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
and the linked Windows distributor. Keep its installation directory dedicated
to that tool. Supply the absolute installed executable path to the server/test
process; clients cannot choose an executable.

From the dedicated verification checkout, use the backend's configured Python
environment. Example PowerShell, adjusting both executable paths:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'backend/src'
$env:FAIRMADE_TESSERACT_PATH = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$env:FAIRMADE_RUN_LOCAL_RECEIPT_EVAL = 'true'
& 'C:\path\to\configured\python.exe' -m pytest -q -s --tb=line `
    -c backend/pyproject.toml backend/tests/receipts/test_local.py
```

The synthetic image cases exercise both PNG and JPEG through normalization,
real English OCR, real Qwen extraction and authenticated API requests. They
verify exact extracted totals, no expense before approval, import retries,
seller category review, stale approval rejection, approval exactly once, and
expense/draft persistence after application restart. Fixture databases are
isolated; the production API and frontend are unchanged.

The separate text-model case uses synthetic OCR text through an OCR double.
Its pass is not a substitute for the two actual image cases. General photo,
handwriting, localization, ambiguous totals and real receipt accuracy still
require representative evaluation and human factual review.

See [the receipt contract](receipt-expenses.md) for server feature flags,
privacy, supported formats, explicit review and local MVP limitations.
