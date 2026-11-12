# Receipt extraction and reviewed expenses

The [real verification checklist](receipt-verification.md) distinguishes actual
PNG/JPEG OCR checks, real text-model checks and provider doubles. The full backend
workflow passed with local Tesseract 5.5.3.20260724 and Qwen on 2026-11-11;
frontend receipt-upload/review acceptance remains separate.

Implemented backend proposal; frontend acceptance and integration are pending.
The user chose local Tesseract OCR plus the existing Ollama/Qwen3 8B text model.
Neither component is downloaded automatically by an API request. No paid service,
cloud fallback, image model or new Python runtime dependency is introduced.

## Workflow and authority

Upload one synthetic JPEG/PNG receipt, receive a private extracted draft, edit
its details, review its exact preview hash/revision and explicitly approve it.
Only approval records an immutable seller-reviewed, unverified expense snapshot.
Extracting a draft alone records no expense. Repeated identical approval returns
the same expense. Inventory, recipes, production analyses, supplier quotes,
public Passports, payments and existing sales profitability reports are unchanged.
Approved expense aggregates are now available to
[seller assistant history questions](assistant-receipt-expenses.md), separately
from modeled production costs and sandbox sales profit.

The model sees bounded, best-effort-redacted OCR text only. It receives no private
product records, account details, prior chat history or receipt image. OCR text
is untrusted data, never instructions. Unknown fields remain null. The server
checks that extracted merchant/date/item text occurs in OCR and that extracted
amounts occur as numeric values. This does not prove the model assigned an amount
to the correct field. Human factual review remains necessary.

Only ISO YYYY-MM-DD dates are converted automatically; ambiguous local date text
remains in extracted.date_text for manual review. USD is extracted only from
explicit USD or US$ text; a bare dollar sign does not establish currency.
Seller edits can correct fields beyond OCR, but remain seller-reported.
Category defaults to other and is selected by the seller, not inferred by AI.

## API contract

All routes require a current verified seller and owner scope, including browsing.
Buyer accounts receive 403. Other-owner IDs return 404. All responses, including
errors, use Cache-Control: no-store. UUIDs are strings; timestamps are UTC.
Money is a nonnegative USD decimal JSON string with at most two fractional places
and at most 1,000,000,000. Floats and numeric JSON money are rejected.

| Route | Method | Result |
| --- | --- | --- |
| /api/v1/seller/receipt-drafts | POST | Extract private ReceiptResponse, 201 |
| /api/v1/seller/receipt-drafts | GET | Owner draft/history page, 200 |
| /api/v1/seller/receipt-drafts/{id} | GET | Owner draft, 200 |
| /api/v1/seller/receipt-drafts/{id} | PUT | Replace editable details at current revision, 200 |
| /api/v1/seller/receipt-drafts/{id} | DELETE | Discard unapproved draft, 204; absent ID is 404 |
| /api/v1/seller/receipt-drafts/{id}/approve | POST | Record/retrieve exact reviewed ExpenseResponse, 200 |
| /api/v1/seller/expenses | GET | Owner immutable expense page, 200 |

Both collections use the existing limit/offset convention, descending created_at
then id order, and {items, limit, offset} responses. There is no public receipt,
image retrieval, receipt search, update to approved records or expense delete API.
Future corrections/voids need their own explicit financial-history design.

Import body: {request_id: UUID, image_base64: string}. Base64 contains raw image
bytes, not a data URI, URL or filename. The request ID is unique per account.
An identical retry returns the same draft without OCR/inference; a changed image
under that key returns 409 REQUEST_ID_CONFLICT. The same byte-identical image
under a new key returns 409 RECEIPT_ALREADY_IMPORTED. This is not semantic
duplicate-receipt detection: a recrop, different photo or metadata change can
have different bytes. Review duplicates before approving. Discarding a draft
removes its source hash/retry key, allowing a new import.

ReceiptResponse contains id, request_id, source_hash (SHA-256 of supplied bytes),
revision, state (draft/approved), redacted ocr_text, immutable extracted fields,
editable details, processing provenance, created_at, updated_at, approved_at,
preview_hash, approval_blockers and notices. Images, local paths, account IDs,
tokens and subprocess output are never returned. Provenance identifies
receipt-ocr-v1, Tesseract/eng and Ollama/qwen3:8b; it is not source verification.

Extracted fields are merchant, date_text, currency, subtotal, tax, total and items.
Each item has description and nullable line_total (the printed line total, not
unit price or quantity). Nulls are preserved. At most fifty lines are supported.

Edit body example with illustrative synthetic data:

~~~json
{
  "expected_revision": 1,
  "details": {
    "merchant": "Synthetic Store",
    "purchased_on": "2026-11-10",
    "currency": "USD",
    "subtotal": "10.00",
    "tax": "0.80",
    "total": "10.80",
    "items": [{"description": "Flour", "line_total": "10.00"}],
    "category": "materials"
  }
}
~~~

Details support nullable merchant, purchased_on, currency, subtotal, tax, total,
items (default empty) and category (default other). Categories: materials,
packaging, transport, utilities, equipment, overhead, other. Editing increments
revision and changes the preview hash without overwriting OCR/extracted evidence.
expected_revision must be a strict integer; booleans are rejected.

Approval body example with an illustrative hash placeholder:

~~~json
{
  "expected_revision": 2,
  "preview_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "approved": true
}
~~~

Use the actual hash returned by the latest receipt GET/PUT, not this placeholder.
Approval requires merchant, confirmed purchased_on, USD currency and positive
total. Decimal arithmetic checks subtotal + tax = total when all are known,
subtotal cannot exceed total, and fully known item totals must match subtotal,
or total minus tax when subtotal is unknown and those values are known.
Missing components are unknown, not assumed zero. Discounts/returns, negative
lines, multi-currency and allocations are not modeled. Resolve mismatches by
reviewing the actual receipt and correcting the details; do not invent balancing
values. Drafts can retain unresolved fields; approval is blocked until resolved.

ExpenseResponse contains id, receipt_id, frozen details, created_at and
basis: seller_reviewed_unverified. Approval and its expense snapshot commit
atomically. A stale hash/revision returns 409 REVISION_CONFLICT; incomplete or
inconsistent data returns 409 RECEIPT_REVIEW_REQUIRED. Approved records cannot
be edited/discarded; attempting discard returns 409 RECEIPT_APPROVED.

## Local setup

Install Tesseract with English language data using the
[official installation guidance](https://tesseract-ocr.github.io/tessdoc/Installation.html).
For Windows, the manual links the UB Mannheim build; installation may require
administrator interaction. Review the installer/version/provenance rather than
silently downloading an arbitrary executable. After earlier automated setup was
blocked, the user installed version 5.5.3.20260724 with English data. Real synthetic
PNG/JPEG extraction, seller review, approval and restart checks now pass; see the
[verification evidence and limitations](receipt-verification.md).

Use the existing configured backend environment and run migrations to current head.
Receipt tables were introduced in 0027; later application migrations still apply.
Then configure the server process, adjusting the local executable path:

~~~powershell
$env:FAIRMADE_TESSERACT_PATH = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
$env:FAIRMADE_RECEIPTS_ENABLED = 'true'
$env:FAIRMADE_ASSISTANTS_ENABLED = 'true'
# Start Ollama with the existing qwen3:8b model and start the backend normally.
~~~

An absolute FAIRMADE_TESSERACT_PATH is server-controlled configuration. Without
it, the server searches PATH. Clients cannot select an executable or arguments.
The [Tesseract command](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
uses English, LSTM OCR and page-segmentation mode six on a temporary normalized
image. Its timeout is twenty seconds with one OpenMP thread and no captured
process logs. Temporary files are removed on completion/failure. OCR and model
inference share the existing single-process inference slot.

Creation also requires the assistant gateway. Read/edit/approve/discard do not
require OCR or inference availability. OCR disabled returns 503 RECEIPTS_DISABLED;
missing/failed/timed-out OCR returns 503 OCR_UNAVAILABLE. Existing assistant
503/502 and 429 ASSISTANT_BUSY apply. Errors are sanitized; validation does not
echo the uploaded base64 or raw body. Format is {detail: {code, message}}, except
redacted validation detail arrays.

## Limits and retention

Initial limits: one JPEG/PNG, five MiB decoded input, at most 6000 pixels per
side/twelve million pixels, no animation/PDF/multipage input, 16,000 UTF-8 OCR
bytes, fifty line items and two hundred retained receipts per seller. Base64
and field lengths are bounded. The cap includes approved provenance; approved
history cannot be discarded to free capacity. These are implementation limits,
not separate confirmed user choices. More capacity requires a reviewed change.

Receipt images are transient and not stored in the database. Redacted OCR,
extraction and reviewed expense evidence persist locally; the chat's thirty-day
retention policy does not apply to these business records. Owners can discard
unapproved drafts. Approved history has no automatic expiry/correction/erasure
workflow in this implementation. Set business-record/backup retention policy
before hosted use; use synthetic data for the demo.

Payment-related lines, email addresses and long digit sequences are removed on
a best-effort basis before inference/storage. This is not comprehensive personal
data detection. Do not upload sensitive/unrelated documents. There is no new
encryption or secure erasure of database/temp/backup storage. Host readiness
also requires resource-isolated decoding/OCR, overall request/concurrency and
storage quotas, abuse controls, redaction evaluation and operational monitoring.

Migration 0027 adds receipt_drafts and receipt_expenses, account/retry/image
constraints, one expense per receipt, revision/state/approval checks and owner
list indexes. Downgrade refuses receipt/expense history and preflights existing
protected history before wider nontransactional SQLite rollback.

## Frontend and evaluation handoff

Frontend should provide image selection, extraction loading/error states, the
private OCR/evidence preview, editable details, approval blockers and exact
explicit review. Preserve retry keys during network retries. Render text safely,
handle missing fields and do not imply that OCR or seller approval verifies a
purchase. Display the expense separately from sales profit and inventory.
No frontend edits or browser/end-to-end demonstration are included.

Automated tests isolate OCR and model boundaries and check totals, review state,
duplicate/retry handling, ownership, revocation, rollback, concurrent approval,
temporary cleanup and migration preservation. Real Qwen evaluation on synthetic
OCR text is separate from real Tesseract image OCR.
Once Tesseract is configured, run the opt-in synthetic full workflow:

~~~powershell
$env:FAIRMADE_RUN_LOCAL_RECEIPT_EVAL = 'true'
# From a feature checkout with its backend/src on PYTHONPATH:
python -m pytest -q -s -c backend/pyproject.toml backend/tests/receipts/test_local.py
~~~
