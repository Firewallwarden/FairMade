# Frontend integration and acceptance

The frontend uses the implemented HTTP contracts in [the shared API contract](../docs/api-contract.md). Backend authorization, deterministic calculations, ownership, revisions and payment verification remain authoritative. This handoff changes no backend implementation or API shape.

## Implemented experiences

| Area | Where to find it |
| --- | --- |
| Accounts | Account: registration, memory-only login, seller intent/status and account refresh |
| Administrator review | Account > Review seller applications: queue/detail and revision-safe final decisions |
| Product economics | Seller workspace > product > Calculate: analyses, margins, scenarios and break-even |
| Recipes/production | Product > Recipe costing / Completed production: saved snapshots and corrections |
| Quality history | Product > Quality Lock: mandatory standards, reported checks and historical details |
| Comparisons/sourcing | Product > Compare / Supplier savings: observations, quotes, exclusions and recommendations |
| Supplier records | Seller workspace > Private supplier records: profile changes, experiences, history and reliability |
| Materials/livestock | Seller workspace > Material inventory / Livestock records: quantity and attribution histories |
| Publication | Product > Review & publish: saved draft edits, preserved disclosures, fresh previews, approval and withdrawal |
| Presentation | Product > Photos & description: private images and model-assisted copy review; storefront settings |
| Discovery/planning | The market / Meet the makers: filters, radius searches, Passports, comparisons, favorites and basket/pair planning |
| Assistants | Ask FairMade: start from buyer listing or seller product, select private context, reopen saved conversations |
| Receipts | Seller workspace > Receipts & expenses: import, extracted unknowns, corrections, saved-preview approval and expenses |
| Orders/refunds | Orders > My purchases / My seller orders: messages, pickup/history, cancellation, refund lists/inbox and controls |
| Sales/reports | Seller workspace > Itemized sales report; product > Business reports for aggregate sales, insights, forecasts, calendar and advice |

Older analyses, quality evidence, observations/comparisons, sourcing inputs, quotes/reports, pricing reviews, Passport drafts and publications have navigable pages. Selections remain explicit across pages. Missing costs, fees, availability or evidence are not turned into zeros or certifications.

## Verification evidence

The reproducible harness and provider setup are in [e2e/README.md](e2e/README.md). The final run record and exact limitations are in [e2e/ACCEPTANCE.md](e2e/ACCEPTANCE.md). Use that record for current passed, skipped and blocked cases; implementation does not imply acceptance.

The suite uses a fresh migrated SQLite database, synthetic accounts and the normal administrator-review workflow. Website actions trigger real backend requests. Its endpoint audit excludes API fixture preparation and records no credentials or bodies. Desktop and narrow Chromium are tested; this is not a full accessibility audit or Safari/Firefox coverage.

Historical [PayPal verification](../docs/paypal-verification.md) and [receipt verification](../docs/receipt-verification.md) remain evidence of their documented provider/backend runs. They do not establish that the latest frontend SDK, receipt editor or refund UI passed current browser acceptance.

## Provider and local-development boundaries

Ollama qwen3:8b is connected through the existing loopback backend gateway. Availability depends on the running service and backend enablement, not installation alone. Model prose, backend facts and source limitations remain separate. There is no automatic cloud fallback, retailer scraping or live price discovery. AI copy requires seller review and separate publication.

Receipt OCR requires Tesseract/English plus the local extraction model. Actual receipt acceptance requires a private image and reviewed ground-truth values. Unknown extracted fields cannot silently become approved spending.

PayPal is sandbox only, enabled by server configuration. The SDK uses backend creation, verified capture and reconciliation. Approval clicks, seller refund approval and uncertain responses do not confirm completion. Use a separate sandbox buyer and keep secrets out of VITE_ variables and Git. Record the latest credentialed-browser result rather than unconditionally claiming PayPal is disabled or verified everywhere.

Sessions stay in memory and expire/revoke on the backend. Reload requires login. Page-local retry identifiers survive uncertain requests while that page remains open; inspect saved orders/drafts before creating another attempt.

## Review and integration

PRs #83-#95 contain implementation and acceptance fixes. Browser-suite and handoff PRs include their prerequisites and remain draft while those prerequisites are unmerged. Every PR targets main. Refresh and revalidate after prerequisite squash merges; merging a stack in order alone is insufficient. No feature PR merge or production deployment is authorized by this handoff.

Follow [local development](../docs/local-development.md) for persistent services outside worktrees. Run checks in dedicated feature worktrees. Verify fairmade-source-revision metadata against the published head before presenting a review demo; a stale central runtime does not demonstrate integration of unmerged changes.

On 2026-11-12, the review website at http://127.0.0.1:5174/ was checked in Chromium:
its source metadata matched published browser PR #96 head
`b3a2116a8c63c0e8dc62e69b4ac013c2e0d7bc38` and reported `clean`.
The marketplace rendered and its API proxy returned 200 from the retained backend
on port 8000. The separate central frontend on port 5173 still serves snapshot
`16309c03ab36f445b30ed710aece35c13ee95543`; use port 5174 to review the new features.
This temporary review server runs from its feature worktree. Its startup does not
refresh the retained runtime snapshot, enable providers or merge feature PRs.
