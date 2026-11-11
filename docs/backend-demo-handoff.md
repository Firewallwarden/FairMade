# Backend review and demonstration handoff

Snapshot: 2026-11-11. Main remains
`16bd9c03933b176fc67c325c3a30932ee16e869b`. This guide describes open
implementations and local validation; it does not authorize merges or assert
that those features are on main.

## Review dependencies

Every PR targets main. “Parent” below identifies the development dependency,
not the GitHub destination. A draft's main-targeted diff includes its unmerged
ancestors. Review the feature increment against its parent while evaluating
that cumulative diff.

| PR | Feature | Direct development parent(s) |
| --- | --- | --- |
| [38](https://github.com/Firewallwarden/FairMade/pull/38) | Local seller/buyer assistants | Main |
| [39](https://github.com/Firewallwarden/FairMade/pull/39) | Sales/cost history | 38 |
| [40](https://github.com/Firewallwarden/FairMade/pull/40) | Supplier explanations | 39 |
| [41](https://github.com/Firewallwarden/FairMade/pull/41) | Description drafts | 40 |
| [42](https://github.com/Firewallwarden/FairMade/pull/42) | Saved conversations | 41 |
| [43](https://github.com/Firewallwarden/FairMade/pull/43) | Receipt review | 42 |
| [44](https://github.com/Firewallwarden/FairMade/pull/44) | Receipt questions | 43 |
| [45](https://github.com/Firewallwarden/FairMade/pull/45) | Buyer personalization | 44 |
| [46](https://github.com/Firewallwarden/FairMade/pull/46) | Basket planning | 45 |
| [47](https://github.com/Firewallwarden/FairMade/pull/47) | Observed-sales forecast | 42 |
| [48](https://github.com/Firewallwarden/FairMade/pull/48) | Order messages | 45 |
| [49](https://github.com/Firewallwarden/FairMade/pull/49) | Public evidence ordering | Main, independent |
| [50](https://github.com/Firewallwarden/FairMade/pull/50) | Seller insights/alerts | 44 |
| [51](https://github.com/Firewallwarden/FairMade/pull/51) | Product pairs/bundles | 46 |
| [52](https://github.com/Firewallwarden/FairMade/pull/52) | Supplier review modes | 42 |
| [53](https://github.com/Firewallwarden/FairMade/pull/53) | Composition explanations | 42 |
| [54](https://github.com/Firewallwarden/FairMade/pull/54) | Conditional price advice | 42 |
| [55](https://github.com/Firewallwarden/FairMade/pull/55) | Saved cost calendar | 50 |
| [56](https://github.com/Firewallwarden/FairMade/pull/56) | Consistent economic selection | 54 and 55 |

The economic-selection compatibility follow-up #56 combines #54 and #55 and
therefore depends on #38–#44, #50, #54 and #55. This documentation branch is
based on #47 (and therefore #38–#42); its references to other features do not
make those implementations part of its tree.

Only #38 and #49 were ready at this snapshot. All dependent implementations
remain draft. **Do not squash-merge this table consecutively.** After each
parent merge the agent must fetch, verify the merge commit on origin/main,
refresh affected published children by normally merging current main into
their branches, resolve both sides, push, revalidate and run the Review guard.
A child can become ready only after all its prerequisites are verified.
The [integration incident procedure](stacked-pr-integration.md) explains why
squashing in order alone does not refresh descendants. No main merge or
published history rewrite was performed by this validation work.

## Combined validation

A dedicated local branch, `integration/assistant-backlog-validation`, combines
all eighteen published feature heads #38–#55 and fix #56 for testing. It is separate from
main and is not a deployment or merge-ready integration PR. Source/test changes
live in its dedicated worktree, outside the primary main checkout.

The local validation commit is
`1a2cb844110b04f63cfa2a96386ac0dd35901c12` (unpublished artifact, not main).
Checks completed:

- Seven real local Qwen dialogues passed (fourteen turns), including buyer/seller
  restart continuity, product pairs, composition and conditional price advice.
- Five combined-scope/economic-selection regressions passed on the combined tree.
  The separate compatibility branch passed 181 related tests, with three opt-in
  model evaluations skipped in that particular run.
- Ruff lint/format passed for 422 checked Python files.
- OpenAPI has 194 unique operations, all references resolve, and every pending
  seller/buyer scope extension is retained.
- Alembic has one head, 0029. Disposable upgrade/downgrade/re-upgrade succeeded;
  all 54 tables match application metadata.
- All 35 example JSON files and 230 existing local documentation links passed;
  the two handoff documents passed 29 local-link checks separately.

The full suite is rerunning with persistent JUnit/text output under
`backend/.pytest_cache/combined-validation.xml` and `combined-validation.log`.
An interrupted tool session lost access to the earlier run's final summary;
its result is not claimed. The final captured result will replace this note.

The integration check reproduced one interaction issue: with a newer analysis
present, price advice selected the saved review's analysis while the insight
report independently selected the latest analysis. The compatibility fix passes
the already resolved selected analysis to insights. Regression coverage includes
stateless selection and saved follow-ups across application restarts. Calendar
history still intentionally covers its own labeled historical window.

Shared merge review must preserve all optional seller scope fields and their
validators, buyer listing/basket/bundle selection, each qualitative context/fact
adapter, current source/authorization rechecks, route registration and private
validation redaction. Schema 0029 follows 0028, 0027 and 0026; there must be one
Alembic head. Keep the latest application version when combining branches.
Formatting, OpenAPI compatibility and route/schema checks need to run on the
actual resulting tree. An earlier local combination is evidence to aid review,
not a substitute for revalidation after real main merges.

## Browser assistant handoff

Frontend owns the interface and acceptance of the proposed additive contracts.
Use each feature PR's documentation/examples and generated OpenAPI from the
integrated checkout. Existing [conversation](assistant-conversations.md) and
[assistant](local-assistants.md) contracts describe the foundation.

1. Authenticate a general account; buyer is the default role. Grant seller
   access only through the existing verification process. Keep bearer tokens
   out of URLs, logs, screenshots and the video.
2. Create or select an owned conversation with its explicit buyer/seller scope.
   Restore paged turns after reload. Display conversation revision and handle
   retry identifiers, stale revisions, expiry, logout and deletion safely.
3. Render exact server facts separately from cited qualitative AI paragraphs.
   Missing costs/composition/quality evidence stay unknown. Explain that local
   model failures are errors and do not trigger a cloud fallback.
4. For seller demonstrations, choose current owned sources deliberately:
   production analysis, pricing review or supplier report. Optional insights,
   calendar, forecasts, recipe inputs and bundles retain their saved scope.
   Recheck sources on every follow-up; do not reuse an old answer when its
   evidence or access changes.
5. For buyers, use approved published disclosures only. Confirm personalization
   opt-in and proposed remembered updates, expose disable/delete controls, and
   preserve hard constraints. Select exactly one listing-set, basket or bundle scope.
   Basket/bundle plans do not place orders or reserve stock.
6. Show an application/browser reload between questions and explain an earlier
   proposed price using refreshed facts. Backend restart continuity is already
   tested; the actual browser restore path still needs frontend verification.

## Suggested short video sequence

Use synthetic sellers/products and clearly label the location, quotes, quality
claims, costs and sandbox transactions as demo data. Do not overwrite real
business data to fabricate long histories.

1. Seller: open a sourdough product, show recipe/yield/labor/overhead costs,
   run the exact economics calculator and a proposed-price simulation.
2. Show a mandatory Quality Lock excluding a cheaper quote. Compare remaining
   usable-unit/transport evidence using a transparent supplier mode.
3. Ask the seller assistant to explain a conditional price result or on-demand
   margin warning. Ask a follow-up, reload, and show retained conversation context.
4. Seller reviews the exact Passport/listing preview and chooses public
   disclosures. Show composition only if explicitly approved.
5. Buyer: discover the storefront, compare unit prices/public evidence, ask why
   the product costs what it does, and show missing data without invented claims.
   Optionally demonstrate a consented preference and an affordable basket/pair.
6. Complete a real PayPal **sandbox** purchase with backend-verified capture.
   Show authoritative order/stock state, a participant message, then a buyer
   refund request that the seller reviews. Confirm status/history on the backend.

Before recording, time the local model on the demonstration machine and keep a
tested shorter path if latency is high. Any prerecorded/model-failure fallback
must be labeled honestly. Do not expose payment credentials, real buyer data or
authorization headers.

## Checks still requiring setup or frontend participation

- Verify the integrated browser routes and accepted contracts with the frontend
  developer; this backend work did not edit or audit their application branch.
- Configure local Tesseract and run a real image-to-draft-to-approved-expense
  smoke test. Image decoding/OCR doubles and real text-model tests do not prove
  the complete scanner is working. Until then, omit scanning or label it pending.
- Run credentialed sandbox create/approve/capture and seller-approved refund
  using the shared development merchant. Test doubles do not establish a live
  provider integration. Production seller-connected merchants remain deferred.
- Review data backups/migration/retention and hosted security separately.
  The local demo does not establish production readiness.

See [the original feature audit](feature-completion-audit.md) for coverage and
remaining limits. Recommended local designs and deeper alternatives are recorded
in the feature PR versions of [the decision log](local-mvp-decisions.md).
Validated seasonality/demand, actual-cost reconciliation, pre-purchase messaging,
multi-seller plans and proactive notifications remain deeper work; they are not
quietly represented as completed features.
