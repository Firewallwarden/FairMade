# Frontend demo and handoff checklist

Use separate synthetic administrator, seller and buyer accounts. See [the integration map](INTEGRATION.md) for navigation and [the browser acceptance record](e2e/ACCEPTANCE.md) for checks actually completed.

## Implemented

- [x] Registration/login/logout, seller intent/status and administrator decisions.
- [x] Products, deterministic pricing, saved analyses and historical review.
- [x] Mandatory Quality Locks and historical rules/claims/checks.
- [x] Recipes, costings, completed production, materials and livestock attribution.
- [x] Supplier records, dated observations/quotes, comparisons and quality exclusions.
- [x] Passport edits, preserved disclosures, fresh approvals and withdrawal.
- [x] Private photos, seller-reviewed copy and storefront controls.
- [x] Marketplace/radius discovery, comparisons, favorites, preferences and planning.
- [x] Saved buyer/seller assistants with explicit private-source selection.
- [x] Receipt import, correction and saved-preview expense approval controls.
- [x] Orders, messaging, pickup/history and unpaid cancellation.
- [x] Buyer refund list, seller inbox and decision/reconciliation controls.
- [x] Itemized/aggregate reports preserving unknown fees and costs.
- [x] Older-record pagination retaining selections.
- [x] Playwright harness using the actual frontend/backend and isolated data.

## Acceptance and demo operation

These are gates, not claims that a provider ran. Use the linked run record for actual evidence and outstanding requirements.

- Check build, lint, unit tests and browser-suite TypeScript validation.
- Run desktop and narrow-screen projects; inspect failures and explicit skips.
- Run real Ollama continuity, saved-history reopening and failure cases.
- Supply a private real receipt image and reviewed values; exercise extraction, corrections, approval and expense lookup through the latest frontend.
- Supply server-only PayPal sandbox settings and a separate sandbox buyer; exercise approval, backend-verified capture, pickup/history, refund approval/denial and uncertain-outcome recovery. An approval click is not payment completion.
- Check assistant, receipt and refund entry points, loading/empty/error/retry states and keyboard access.
- Confirm demo HTML source revision equals deployed main; source state is clean for a checkout or exported-snapshot for an identified runtime export.

## Controlled integration

- Merge feature PRs only when explicitly authorized; verify their merge commits on fetched main.
- Keep dependent PRs draft against main until prerequisites are integrated and children are refreshed, revalidated and pass the readiness guard.
- Preserve private runtime settings/data outside Git. Retire worktrees only after services, dependencies and IDE handles no longer reference them.
- Shipping, production payouts, hosted security and live payments remain outside this local sandbox workflow.
