# Backend conversational-continuity audit

The initial audit after assistant PRs #39, #40 and #41 found no retained
conversation memory. Separate question calls did not replay a previous proposed
price; business sales/history and description drafts were not dialogue memory.

The user subsequently selected **option 2: saved database conversations**.
The [conversation contract](assistant-conversations.md) documents the implemented
API, retention limits, current-evidence protection and frontend handoff.
[PR #42](https://github.com/Firewallwarden/FairMade/pull/42) contains this follow-up
and remains draft pending prerequisite #38-#41 integration and branch refresh.

## Finding: bounded backend continuity implemented

Seller and buyer conversations now persist scope, completed questions and
answers, revisions, validated scenario inputs and resolved history periods.
They survive application restarts and can resume under a later valid session
for the same account, within retention. Each conversation is bound to its
authenticated owner, assistant role and immutable selected scope.

Follow-ups include up to six recent dialogue pairs within a byte budget. A
seller's prior explicit proposed price can be recalculated from current selected
economics when referenced again. Exact numeric facts and financial outcomes
remain deterministic. Buyer context remains limited to approved public evidence.

The implementation reloads evidence and access before/after inference and before
committing. Prior assistant text is omitted when its evidence or selected price
scenarios changed; an old explanation cannot stand in for a new scenario.
History returns null for old answers whose evidence no longer matches; withdrawn
sources block reads and further questions. Deletion, expiry, roles and owner
boundaries remain independent of whether Ollama keeps its weights loaded.

## Verification

Combined backend regression: **1,251 passed, 13 opt-in checks skipped**.
Two additional access/offline checks added after collection passed separately.
Two real local-model two-turn/restart checks also passed separately. Ruff lint
and formatting passed (329 Python files), along with 119 local documentation
links, three request examples, seven PowerShell blocks and six authenticated
conversation OpenAPI operations. Four existing framework warnings were reported;
no test failures remained.

Automated tests cover two-turn seller/buyer context, restart recovery, current
analysis recalculation, replaced explicit prices, retained resolved history
periods, history access and stale-answer suppression, independent endpoint
isolation, cross-account/role boundaries, revocation, source withdrawal,
idempotent retries, concurrent revision writes, deletion during inference,
expiry/physical purge and transactional rollback. Migration tests check
metadata parity, upgrade/downgrade, preservation and protected-history refusal.

Separate opt-in checks used real local Ollama/Qwen3 8B with synthetic temporary
databases. Both seller and buyer completed a first question and a reference
follow-up after a fresh application instance loaded the saved database.
The seller's second answer retained the eight-dollar scenario and returned
recalculated facts; buyer output remained within public disclosure scope.
These checks establish bounded backend mechanics, not universal model
understanding or a guarantee against hallucinations.

## Browser and backlog handoff

The frontend developer still needs conversation selection, safe text rendering,
paged history restore, retry/revision handling, facts/citations/notices, stale
answer states, deletion and auth/expiry handling. Browser and screen-recorder
integration/latency have not been tested here.

The user restarted the continuous cycle and approved local Tesseract plus Qwen3
for receipts. [Receipt review](receipt-expenses.md) and
[receipt-expense questions](assistant-receipt-expenses.md) now have backend
implementations. Tesseract installation and full image OCR validation remain
pending. [Opt-in buyer personalization](buyer-personalization.md) now connects
confirmed profile preferences, favorites and verified sandbox purchases to buyer
answers. Remembered-preference proposals read owned saved buyer questions and
require confirmation. Profile erasure clears derived answer copies while
original user messages have separate conversation deletion controls.
Single-storefront [basket plans](buyer-basket-optimization.md) now support saved
buyer follow-ups with recalculated stock, constraints and profile memory.
Forecasting and multi-seller basket plans remain follow-ups; browser integration is pending.

Thirty-day inactivity expiry and history/resource caps are documented
implementation limits. Durable storage is the confirmed user choice. Scheduled
physical cleanup, backup retention, encryption/secure erasure and hosted operating
controls remain follow-ups in [the decision register](local-mvp-decisions.md).
