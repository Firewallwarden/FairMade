# Frontend browser acceptance record

Original runs were executed locally on 2026-11-12, using the combined unmerged feature tree based on
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

## Integration refresh before PR #96 merge

After PRs #83-#95 were squash merged and verified on fetched main `34b467c`,
the suite branch was refreshed to include those exact merges. Its remaining diff
contains only browser tooling, source identity and evidence documentation; no
application or backend changes remain. Build, lint, all 49 unit tests and browser
TypeScript passed. Refreshed desktop/narrow Chromium run
`f72b9d1c-4f60-4703-b5df-0baee8533924` passed 64 checks with 14 explicit provider
skips, zero failures and zero retries. Earlier live-provider evidence and the
remaining receipt/PayPal/mobile-provider limitations above still apply.

## Subsequent real-provider acceptance

On 2026-11-12, the backend verification workflow exercised the unchanged application
from main `d1039f4` with real Ollama 0.24.0 / `qwen3:8b` and Tesseract
5.5.3.20260724, using the synthetic receipt image documented in
`docs/receipt-verification.md` and its known reviewed values. Run
`5e052632-beac-4776-a48a-89075851ef67` passed **12 checks, zero failures and
zero skips**, including two setup checks. Both desktop and narrow Chromium passed:

- Buyer and seller referential follow-ups and reopening persisted conversations.
- Consent-based preference proposals and a separately reviewed save.
- Generated description review, editing and private approval.
- Receipt image upload, real OCR/model extraction, reviewed corrections, explicit
  saved-preview approval and recorded-expense lookup.

The first run exposed two test defects: the final merchant text selector matched
both a record heading and a preview value, and the mobile project reused the
desktop seller's imported image. The corrected test targets the expense heading,
checks the recorded expense ID, and creates a separate normally approved synthetic
seller for each receipt case. Backend duplicate protection is unchanged. The
initial failures remain in run `663ecd2d-831f-45a9-bc95-ccf8b0c839a5`.

This closes the local-model/mobile and synthetic-image OCR browser gates above;
it does not establish representative personal receipt/photo accuracy. PayPal
merchant credentials were separately authenticated successfully against the real
sandbox OAuth endpoint, but checkout/refund browser cases still require the
separate private sandbox Personal buyer login. No paid/refunded state was invented.

## Credentialed PayPal browser acceptance

After the sandbox Personal buyer login was supplied privately, run
`17c78e5b-a8d6-46f0-9e18-3be1e6933717` passed **6 checks, zero failures and zero
skips** in 1.9 minutes, including two setup checks. Desktop and narrow Chromium
each completed a real sandbox purchase followed by seller-approved refund and
a separate purchase followed by seller denial of the refund request.

The scenarios verified backend capture, eligible review creation/edit/withdrawal,
seller pickup changes and buyer pickup history, populated buyer/seller refund
lists, populated itemized sales, and recovery after deliberately dropping the
approval response **after the real backend refund request**. The isolated database
retains four completed checkouts, two verified refunds and two denied requests.
The persistent demo database was not used for these new transactions.

The previously unexecuted test helper needed provider-UI corrections: select the
visible SDK frame; wait for the accessible Next/Log In steps before filling the
password; recognize the current Pay approval button; and wait for the in-flight
network handler before removing it. Earlier failed runs remain retained; they do
not indicate failed payments merely because a selector or assertion failed. In
particular, run `248bcb87-8706-4b19-ac23-f0327834a528` completed a capture and refund
before exposing the simulated-response handler race.

Together with the 12 real-model/OCR checks above, these results close the selected
local provider gates on desktop and narrow Chromium. They do not imply live
production payments, physical-device Safari/Firefox coverage or representative
personal-receipt accuracy. Credentials, provider bodies and personal receipt
fixtures are not committed, and provider screenshots/traces remain disabled.
