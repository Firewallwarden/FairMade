# Frontend browser acceptance record

Executed locally on 2026-11-12, using the combined unmerged feature tree based on
main `8c27804` plus PRs #83-#95. These results do not establish integration into main.
The suite lives in `feature/frontend-browser-workflows`; run artifacts remain in
ignored per-run directories. Setup assertions count in the totals below.

| Check | Actual result |
| --- | --- |
| Production build | Passed |
| Oxlint | Passed |
| Unit/contract tests | 49 passed, no failures |
| Browser-suite TypeScript | Passed |
| Default desktop + narrow Chromium | 64 passed, 14 explicit provider skips, no failures; run `42a7f896-ccc2-4e42-b5b3-f738db5f530f` |
| Real Ollama buyer continuity + description review/edit/approval | 4 passed including setup, no failures; run `a7ca7cd9-0e87-4880-80a5-e7188c27b625` |
| Real Ollama seller continuity with selected analysis/review | Passed in run `e618c928-ffe6-433d-a478-b99b1b1ecb9a`; that run also contained two failing buyer/description test steps, corrected and rerun separately above |
| Real Ollama preference proposal and separate reviewed save | 3 passed including setup, no failures; run `26d9484d-6a8e-4270-9759-9be6c69f22a6` |

The [workflow matrix](README.md#workflow-coverage) describes scenarios exercised by
the suite. Website requests reach the actual backend. API fixture preparation is
excluded from the sanitized endpoint audit; counts do not imply every state,
permission combination or backend route was exercised. The final default run
observed 149 distinct method/routes in 1,103 browser responses. The default provider skips
are buyer/seller live continuity, memory, description, receipt, and two sandbox
purchase/refund cases in each browser project. Live-model checks above were run on
desktop separately; the mobile provider variants remain unexecuted.

## Defects reproduced and fixed

- After Passport withdrawal and a replacement publication, the website advertised
  an older hidden listing as public. PR #84 checks current public availability and
  publication identity before showing that link. Desktop and mobile regression pass.
- New listing photos used public media before approval and rendered as broken
  preview images. PR #95 uses authenticated private images for seller previews.
  Desktop/mobile tests verify loaded pixels while public media returns 404, then
  anonymous access after explicit approval.

## Known limitations and uncompleted gates

- Receipt browser acceptance needs a private real receipt image, reviewed values,
  Tesseract/English and enabled local extraction. No image/ground-truth fixture was
  supplied. Extraction, correction, approval and expense lookup are authored cases,
  not completed current acceptance.
- PayPal browser acceptance needs server-only sandbox configuration and a separate
  sandbox buyer. No private buyer credentials were supplied. Verified capture,
  eligible review create/edit/withdraw, populated refund lists, pickup updates and
  history, approval/denial and uncertain-refund recovery are authored but unexecuted.
  External PayPal selectors may require adjustment during credentialed acceptance.
- Itemized sales and refund inboxes passed empty-state/date/retry checks. Populated
  paid-order reporting remains part of the payment gate; no fake paid statuses or
  invented fees/costs were inserted to produce a green report.
- The backend memory guard rejects an explicit amount written as `8 USD` with
  `502 ASSISTANT_INVALID_RESPONSE` / "Budget lacks explicit question support."
  Its current parser accepts `USD 8` or `$8`; the positive test uses supported
  notation. This backend limitation is recorded for the backend owner; no backend
  implementation was changed. An earlier test also incorrectly required `8.00`
  instead of accepting the backend's valid decimal string `8`; that assertion was
  corrected and the complete positive workflow rerun successfully.
- Assistant timeout coverage aborts browser transport and verifies retry identity,
  then exercises the real disabled-provider error. It does not claim a live model
  exceeded the backend timeout. Revocation, deletion and unavailable-source cases
  are covered separately.
- Narrow Chromium uses iPhone viewport/touch settings. Safari, Firefox, a full
  keyboard audit of every control, and a formal accessibility audit were not run.

## Reproduce and inspect

Follow [README.md](README.md) for isolated setup and provider variables. Use
`npm.cmd run test:e2e:report` for the latest HTML report, or
`node e2e/open-report.mjs <run-id>` for a specific run. Preserve private fixtures
outside the repository. Never turn a skipped/failed provider case into a claimed
success or bypass backend verification.

Before a review demo, rebuild/restart from the clean published feature head and
check the served `fairmade-source-revision` and `fairmade-source-state` metadata.
The persistent central runtime may still serve an earlier snapshot.
