# Real receipt verification

This check uses actual Tesseract and local Ollama/Qwen3 over clearly synthetic
receipt images. It does not require uploaded personal receipts, paid inference,
frontend changes or modifications to production business data.

## Current evidence

On 2026-11-11 (America/Chicago), the user installed UB Mannheim Tesseract
5.5.3.20260724 at `C:\Program Files\Tesseract-OCR\tesseract.exe`. Its version and
English language data were checked. The existing loopback Ollama service and
`qwen3:8b` model were available; no model was downloaded.

The full receipt suite passed **29 tests with no skips**, including two real
image cases (PNG and JPEG) and two real Qwen extraction cases (readable and
unreadable synthetic OCR text). The image cases use the real Tesseract process
and real Qwen model through authenticated APIs; they verify import retries,
no expense before approval, seller correction/category review, stale approval
rejection, approval exactly once and persistence after application restart.
Warm-model image workflow times were 1.90 seconds for PNG and 1.83 seconds for
JPEG on this machine; these are observations, not a latency guarantee.

The first full image run exposed an OCR ambiguity: the printed tax `0.80` was
recognized as `@.80`, and Qwen guessed `0.80`. The unchanged evidence validator
correctly rejected that unsupported value. Extraction instructions now explicitly
require null for unreadable numeric characters and prohibit deriving tax from
the other totals. The unchanged image fixtures then passed: tax remained unknown
in the draft, and the simulated seller supplied `0.80` during explicit review.
An offline regression also confirms that a model still guessing that tax gets
502 and saves neither a draft nor an expense. Evidence validation was not relaxed.

JUnit output, logs and isolated fixture databases are retained under the
`FairMade-receipt-ocr-validation` worktree's ignored directory
`backend/.pytest_cache/receipt-ocr-validation/run-20261111-233209/`.
Ruff lint and formatting passed for the three changed Python modules.

Before installation, the image cases were blocked by missing Tesseract. The
earlier text-model-only pass did not establish real OCR. Explicit opt-in still
fails when its OCR prerequisite is missing; default runs skip provider cases.
This successful backend check does not establish frontend receipt-upload/review
integration or representative real-photo accuracy.

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

The separate text-model cases use readable and unreadable synthetic OCR text
through an OCR double. Their passes are not substitutes for the two actual image
cases. General photo,
handwriting, localization, ambiguous totals and real receipt accuracy still
require representative evaluation and human factual review.

See [the receipt contract](receipt-expenses.md) for server feature flags,
privacy, supported formats, explicit review and local MVP limitations.
