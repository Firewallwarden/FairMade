# Seller assistant receipt-expense questions

Implemented additive backend proposal; frontend acceptance/integration are pending.
This extends [seller history questions](assistant-sales-history.md) with the
approved records from [receipt extraction/review](receipt-expenses.md).
There is no new endpoint, provider, migration or automatic business action.

POST /api/v1/assistants/seller and seller saved-conversation turns can now answer
questions about seller-wide reviewed receipt expenses. Existing product ownership,
seller authorization, source revalidation, citation and cache protections remain.
The selected product is still required for the existing seller scope, but receipt
totals are explicitly seller-wide, not attributed to that product.

## Scope and periods

Existing history periods are reused: explicit history_period with UTC start_date
and exclusive end_date, or supported relative phrases such as last month.
Spend/spent/spending/receipt questions now activate the existing bounded history
mode and thirty-date default when no period is supplied.

History answers now add evidence titled Private seller-wide reviewed receipt
expenses before the existing sales and cost-history evidence. Use response-local
evidence_keys and titles, not array positions. Saved follow-ups retain resolved
periods through the existing conversation workflow. No receipt OCR/model setup
is needed to retrieve already approved expense evidence.

Example with an illustrative owned product UUID:

~~~json
{
  "question": "Explain recorded receipt spending and what remains unknown.",
  "product_id": "59a9818e-37a5-47c0-9302-b1b54ab67514",
  "history_period": {
    "start_date": "2026-11-01",
    "end_date": "2026-12-01"
  }
}
~~~

The database query requires the authenticated owner on both the approved receipt
and immutable expense snapshot and filters by seller-confirmed purchased_on,
not OCR save time or approval time. Unapproved drafts, other accounts and the
exclusive end date are excluded. At most two hundred qualifying records are read;
larger reports return 409 ASSISTANT_EXPENSE_REPORT_TOO_LARGE rather than truncate.
Invalid currency/nonpositive/missing total evidence returns 409
UNSUPPORTED_EXPENSE_EVIDENCE. Unsupported data is not silently interpreted as zero.

## Facts, privacy and interpretation

The evidence basis is seller_reviewed_unverified. Data contains start_date,
end_date, currency USD, receipt_count, recorded_total, sorted category_totals
and limitations. Exact Decimal sums render two-place USD values in server facts.
Each entire receipt total uses its one seller-selected category; this is not
item-level allocation. Model context contains qualitative coverage/category
information only. Exact numerical evidence remains separate from AI prose.

No receipt image, raw OCR text, merchant, request ID, expense/receipt identifier
or line-item description is selected for this assistant evidence. Buyer questions
never query private receipt expenses. No payments, stock or production records
are changed. New approved expenses during inference invalidate the answer through
the existing evidence fingerprint check. Older saved answers are withheld when
their current evidence differs.

An empty report means no qualifying approved receipt records were found, not
that the business spent nothing. Receipt approval is a seller review, not bank,
payment, quality, tax or purchase verification. Date/category choices remain
unverified, and unrecorded expenses remain unknown.

**Do not subtract these receipt totals again from modeled profit.** Production
cost estimates may already allocate some of the same spending, and there is no
receipt-to-product or inventory-consumption allocation model. Sandbox capture
reports, saved production costs and receipt expenses are separate evidence
scopes; their totals do not establish accounting net profit.

## Validation and remaining scope

Tests cover exact category/total sums, approved-only inclusion, purchase-date
boundaries, owner isolation, empty coverage, buyer privacy, concurrent evidence
changes, saved conversation follow-ups and refusal of oversized reports. An
opt-in real local-model check separately exercises qualitative explanation.
Frontend should render the new server facts/citations/notices distinctly.

Expense-increase alerts, accounting reconciliation, product allocation,
correction/void workflows, forecasting and buyer personalization are separate
follow-ups, not automatic effects of this read-only extension. Receipt-image OCR
still needs the Tesseract installation and its pending full image smoke test.
