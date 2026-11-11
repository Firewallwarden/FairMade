# Local MVP decisions and follow-up

This register tracks deliberate local-development tradeoffs and existing limits
that need attention as FairMade grows. A local MVP is a working foundation for
testing and development; it is not evidence of hosted or production readiness.

The entries below were reconstructed from the user's decisions and the checked-in
backend documentation at the storefront milestone (#24). Exact earlier decision
dates were not retained. New entries should link their implementation PR, keep a
stable ID, and preserve history when replaced. Update status in the same PR that
changes behavior. Future work here is a backlog, not authorization or a promise
that a design has already been chosen. Frontend implementation/acceptance is
separate from backend availability.

## Confirmed user choices

| ID | Choice and evidence | Current status and limits | Follow-up / review trigger |
| --- | --- | --- | --- |
| MVP-001 | Local testing/development first; hosted readiness deferred. [Backend setup and security](../backend/README.md). | Implemented as a loopback development service with SQLite/Alembic. No hosted deployment claim. | Before shared hosting: decide deployment/database needs; implement appropriate TLS, abuse controls, operational monitoring, backup/restore and recovery, and integration checks. Do not assume SQLite must be replaced without evidence. |
| MVP-002 | Use a shared PayPal sandbox merchant for development; production uses seller-connected merchant accounts. User confirmed before checkout work; [checkout contract](api-contract.md#shared-merchant-paypal-sandbox-checkout). | Implemented sandbox-only backend verification, idempotency and recovery. Credentialed sandbox/browser checks remain pending; shared merchant reporting does not establish seller payouts. | Before live payments: design approved seller onboarding/account connections, permissions, per-seller payment routing/reconciliation and applicable fee/payout behavior; validate sandbox/browser integration first. |
| MVP-003 | One storefront per seller account initially; allow growth to multiple later. User confirmed before [#24](https://github.com/Firewallwarden/FairMade/pull/24). | Implemented independent storefront UUID and plural routes, with a database uniqueness constraint. Account product ownership groups listings. | Multi-store work needs an explicit migration for cardinality and listing assignment, authorization/publication review and a frontend contract. Preserve existing IDs and approval boundaries. |
| MVP-004 | Approximate public seller area for nearby discovery; enhance later. User chose option 1 after #24. [Implementation #26](https://github.com/Firewallwarden/FairMade/pull/26). | Integrated into main by discovery squash merge #26. Seller-chosen representative points require exact storefront publication approval; distances are estimates. Text labels are not geocoded. Existing profiles keep their publications and remain outside nearby search until opting in. | Review location entry/geocoding, precision and disclosure consent, distance semantics and search scaling. Exact business/pickup addresses require a separate explicit decision; do not silently infer or expose them. Preserve these disclosure boundaries in later location work. |
| MVP-005 | Revocable 24-hour bearer tokens. User explicitly approved during account implementation; [authentication contract](api-contract.md). | Implemented fixed expiry and logout revocation. This remains the approved session policy, not a requirement to replace tokens after MVP. | Before hosted browser use, review secure client storage, HTTPS, account recovery, abuse prevention and session management. Any cookie/refresh-token change needs its own design, including CSRF where applicable. |
| MVP-006 | Buyer refund requests require seller approval or denial. User confirmed before [refunds #19](https://github.com/Firewallwarden/FairMade/pull/19); [refund contract](api-contract.md). | Implemented full-order requests, seller decisions and verified sandbox execution/recovery. Partial refunds, appeals and return/restock handling are not implemented. | Preserve seller review unless a new policy is approved. Define partial refunds, appeals, returns, inventory effects and fee adjustments before extending refunds or using live payments. |
| MVP-007 | Estimated profit uses a seller-selected saved production-cost analysis frozen when an order is created. User chose the explicit source option before [#22](https://github.com/Firewallwarden/FairMade/pull/22). | Implemented capture-cohort reports with known/missing coverage, original capture fees and completed refunds. Estimates are not earnings statements; old orders without snapshots stay unknown. | Before accounting/payout reporting: design actual-cost reconciliation, time-period cash flows and refund fee adjustments. Never backfill missing costs from the latest analysis without a separate explicit policy. |
| MVP-014 | Sellers upload product photos directly to FairMade, stored locally for MVP, with managed media storage considered later. User chose option 1 after #26 opened. [Implementation #27](https://github.com/Firewallwarden/FairMade/pull/27). | Implemented and tested in #27, refreshed against the verified #26 squash merge before review. Immutable normalized JPEG blobs in local SQLite let metadata/bytes save or delete atomically, with exact listing publication approval. SQLite media storage is an implementation choice, not an approved production architecture. | Retain publication consent and immutable normalized content when replacing storage. Before hosted use, review managed storage/serving, backup/retention/capacity, isolated image processing with hard time/memory limits, abuse controls, dependency updates and moderation policy. Current limits include JPEG/PNG input, 5 MiB uploads, 16 million pixels/6000-pixel sides, 2048-pixel output sides, 10 photos per product, 64 MiB per seller and six photos per listing. |
| MVP-015 | Pickup-only fulfillment for local MVP; user chose option 1 after #25-#27 merged. [Implementation #28](https://github.com/Firewallwarden/FairMade/pull/28). [Contract and future plans](pickup-fulfillment.md). | Backend implemented and tested in #28: private seller-reported preparing/ready/collected states, instructions and immutable history. Verified payment and refund gates are enforced; collection is not independent handoff proof. | Future decisions: delivery/shipping modes, address privacy/validation/retention, authoritative fees/taxes, schedules/reminders, buyer confirmation or pickup codes, disputed handoff/corrections, partial returns/restocking and hosted operational controls. These follow-ups do not authorize providers, infrastructure or policy changes. |
| MVP-016 | Immediate publication for eligible buyer reviews, without seller approval or selective suppression; user chose option 1 for local MVP after #28 opened. [Implementation #29](https://github.com/Firewallwarden/FairMade/pull/29). [Contract and future plan](product-reviews.md). | Backend implemented and tested in #29, verified integrated on main: explicit publication consent, one review per buyer/product, frozen historical sandbox capture evidence, author edits/withdrawal and generic public labels. Product visibility still controls the whole review page. Claims remain unverified opinions. | Before production, decide platform moderation/reporting/takedown/appeals, moderator permissions and audit, fraud/reversed-verification handling, spam/abuse controls, privacy/retention and edit history, safe frontend rendering and end-to-end checks. Seller replies/media/voting and scaled aggregates require separate decisions. |
| MVP-017 | Manual administrator review of seller applications, with approve/deny outcome, shared reason and audit; user chose option 1 after #29 opened. [Implementation #30](https://github.com/Firewallwarden/FairMade/pull/30). [Contract and future plans](manual-seller-review.md). | Backend implemented and tested in #30, verified integrated on main: additive seller approval, immutable final decision, current admin authorization, account-level self-review prevention and isolated first-admin operator bootstrap with session revocation. No document collection, identity certification or public role-grant endpoint. | Before production, define verification criteria/evidence and document privacy/retention, reviewer responsibilities, MFA/step-up, additional-admin management and recovery, audit monitoring, appeals/reapplication, revocation/reverification, notifications and frontend integration. Bootstrap is first-admin-only, with no silent privilege restoration; use a dedicated reviewer account for local testing. |
| MVP-018 | Manual ingredient quantities and purchase costs for reusable recipe/batch costing; user chose option 1 for local MVP after #30 opened and deferred supplier quotes. [Implementation #31](https://github.com/Firewallwarden/FairMade/pull/31). [Contract and future plans](manual-recipe-costing.md). | Implemented and tested in #31, verified integrated on main: one private current recipe per product, revision checks, dated manual costs, exact compatible quantity conversions and six-place allocated costs, immutable costing plus atomic standard analysis, product-scoped retry keys. No supplier or inventory coupling; one-current-recipe and rounding details are implementation limits. | Before deeper production use, design explicit selected-quote links/frozen provenance, freshness and availability, usable yield/waste and transport/bulk allocation, compatible units and Quality Lock eligibility. Revisit ingredient catalogs, multiple recipes/version archives, receipt evidence, actual production/lot tracking, raw-material inventory/reconciliation, currencies/units, hosted controls and frontend integration. Future designs need separate approval; no automatic substitution or source verification is implied. |
| MVP-019 | Manual quantity ledger for raw materials/supplies; user chose option 1 after #31 opened and asked to track deeper implementation for later. [Implementation #32](https://github.com/Firewallwarden/FairMade/pull/32). [Contract and future plans](manual-material-inventory.md). | Implemented and tested in #32, verified integrated on main: seller-wide catalog, fixed g/ml/item stock basis, exact kg/l conversions, zero-stock creation, receipt/usage/waste/physical-count history, current revision checks, atomic balances/events and material-scoped retry keys. Quantity only; recipe costing remains manually entered and sellable stock is separate. | Deeper work: lots/expiry/handling/traceability, recalls, multiple locations, reconciliation/permissions, archiving/merges, retention/audit, receipt cost evidence, FIFO/weighted-average valuation policy, transport/currency allocations, explicit material/ingredient links and confirmed production consumption/yield, supplier freshness and quality eligibility, reorder alerts/forecasting, hosted operations and frontend integration. These require separate decisions; no accounting policy, safety guarantee or automatic coupling is implied. |
| MVP-020 | Completed batches/production periods only; user chose option 1 after #32 opened and explicitly made the multi-stage alternative an optional in-depth implementation for later. [Implementation #33](https://github.com/Firewallwarden/FairMade/pull/33). [Contract and optional plans](completed-production-records.md). | Implemented and tested in #33, verified integrated on main: private reported actual output/costs, exact shared arithmetic, zero-output cost preservation, immutable product/unit/request/result snapshots, retry keys, linked linear corrections and bounded current/history summaries. Stock remains manual; no pricing preferences or forecast costs are invented. | Optional later: planned/in-progress/completed workflow, scheduling, assignments, reservations, cancellation and notifications. This alternative is not automatically required for production deployment. Flock/animal source context is now covered by DOMAIN-001 below. Separately review actual/recipe comparisons, stock/lot links, fractional output units, cost evidence, overlapping periods/shared allocations, pricing/sales-cost integration, reporting, retention/operations and frontend integration; none is automatic scope approval. |

## Current implementation limits to revisit

### Private messages for existing orders: DOMAIN-008

The user confirmed option 1: order-bound buyer–seller messages, and explicitly
asked to record option 2 (pre-purchase product/storefront inquiries) as a later
improvement. [Messaging contract and frontend handoff](order-messaging.md).
The backend provides private participant-only plain-text sends and cursor
history, with safe retries, current seller authorization and no commerce or
AI-memory side effects. Existing unpaid/cancelled/refunded orders remain in scope.

Two thousand characters per message, one thousand messages per order, ten new
messages per account/minute across orders, read-only history and HTTP polling
are implementation limits, not individual user choices. Messages are retained
with their order without automatic expiry, edit or deletion; this is separate
from AI chat retention and profile erasure. SQLite append serialization needs
review if moving to a database with different write concurrency.

Revisit pre-purchase inquiries with explicit eligibility, contact consent,
privacy, reporting/blocking, retention and abuse policies. Separately review
message erasure/export, backups, inbox/unread state, attachments, read receipts
and notifications. This future entry does not authorize providers, infrastructure
or a broader messaging/contact scope. Browser integration remains pending.

### Buyer personalization and profile memory: DOMAIN-005

The user selected option 2: opt-in activity-based personalization using favorites
and purchase history alongside stated preferences, explicitly emphasizing saved
assistant memory. [Contract and controls](buyer-personalization.md).
Buyer conversations now consume confirmed profile memory; saved buyer questions
can propose budget/type updates for confirmation. Account defaults remain off.
Seller conversations/private records and inferred sensitive traits are excluded.

Thirty-day expiry from the last confirmed update, ninety-day sandbox purchase
signals, two hundred activity rows, one hundred matching candidates, four
suggestions, per-listed-unit USD budgets, published location labels and simple
affinity ordering are implementation limits, not individual confirmed choices.
Disable/delete clears preferences and profile-derived saved answer copies.
Minimal revision tombstones prevent stale-tab restoration; user messages,
favorites and orders have separate deletion/retention policies.

Before hosting, review retention/backup/erasure, scheduled cleanup, larger data
windows, granular consent/monitoring, historical variant semantics, safety
evidence and frontend/browser evaluation. Basket budgets and multi-seller
optimization need separate design. Persistent personalization is the chosen
foundation, not an automatically temporary feature to replace with stateless
behavior after MVP.

### Receipt OCR and expenses: DOMAIN-004

After restarting the continuous cycle, the user chose option 1: free local
Tesseract OCR plus the existing Qwen3 text model for receipt scanning and
expense extraction. [Contract, setup and retention](receipt-expenses.md).
This adds private drafts and exact seller approval to immutable unverified
expense snapshots, without stock, recipe or production-cost side effects.
Approved aggregates now support [seller receipt-expense questions](assistant-receipt-expenses.md);
the assistant sees totals/coverage, not OCR, merchants or item descriptions.

English OCR, JPEG/PNG input, five MiB/twelve million pixels, ISO-only automatic
date parsing, explicit USD extraction, two-place money, fifty items, two hundred
retained receipts, best-effort redaction and persistent business evidence are
implementation limits, not individually confirmed user choices. Ambiguous
fields require seller review. Images are transient; approved records have no
automatic expiry or correction/void workflow. Chat retention does not apply.

Before broader use, review localized dates/currencies, discounts/returns,
semantic duplicate detection, record corrections/voids, expense allocation and
assistant retrieval, retention/erasure/backup policy, isolated OCR/decoding,
abuse/resource controls and frontend integration. The local installer was
canceled; real full image OCR evaluation remains pending until configured.

### Saved conversations: DOMAIN-003

The user explicitly selected option 2: saved database conversations with account
ownership, deletion and a defined retention policy, following the three assistant
extensions and continuity audit. [Contract and retention](assistant-conversations.md).
[Implementation #42](https://github.com/Firewallwarden/FairMade/pull/42) is draft,
dependent on #38-#41, and not yet integrated on main.
This replaces the foundation's stateless-only implementation limit; the original
independent question endpoints still remain stateless.

The implementation uses SQLite, thirty-day inactivity expiry, twenty unexpired
conversations per account, forty turns per conversation and at most six recent
context pairs within twelve thousand bytes. These values are implementation
limits, not individually confirmed user choices. Owners can delete; expiry blocks
reads immediately, while physical cleanup is lazy per owner or an explicit
operator command. No scheduling service is installed.

Before hosted use, review scheduling, database/backup retention and secure erasure,
storage protection/encryption, capacity/abuse controls, model context evaluation,
browser token handling and end-to-end demo behavior. Durable storage was the user
choice, not a requirement to replace it with temporary memory for production.
Further scope/provider changes still need their own authorization.

### Local assistant decision: MVP-021

[Description drafts](ai-description-drafts.md) add durable private generated copy
and seller review, with no automatic application/publication. Generation uses
only selected product metadata; unsupported marketing wording still needs human
factual review. This business-record persistence does not select a conversation
retention policy. The user subsequently chose saved database conversations,
implemented separately with [defined retention](assistant-conversations.md).
See the [updated continuity audit](assistant-continuity-audit.md).

The [supplier explanation extension](assistant-supplier-explanations.md) supplies
selected excluded quote names and failed/unknown checks to the owning seller's
local model as explicitly excluded evidence. This enables grounded failure
explanations; exclusions never enter cost minima or authorize substitutions.
Claims remain unverified, and product-level constraints are not waived.

The [sales/history extension](assistant-sales-history.md) adds bounded saved
analysis comparisons and existing sandbox capture-cohort summaries. English
relative-period phrases, a thirty-date default, twenty-five saved analyses and
the existing one-thousand-sale cap are documented implementation limits.
These are not expense ledgers, forecasts or verified live earnings. Conversation
retention is now implemented separately following the user's durable-storage choice.

The user approved option 1: Ollama with Qwen3 8B locally, with no paid inference.
Implemented and validated in [PR #38](https://github.com/Firewallwarden/FairMade/pull/38)
(1,173 backend tests and eight separate real local-model evaluations).
The [assistant foundation](local-assistants.md) implements separate owner-scoped
seller and approved-public buyer contexts, validated proposed-price extraction,
deterministic financial facts, cited qualitative AI explanations and explicit
failure responses. No cloud fallback, auto-download or autonomous changes.
Frontend integration is pending. This entry records the provider decision;
read-only/stateless behavior, bounded evidence, single-process concurrency and
the original lack of durable conversation history were implementation limits,
not separate user choices. Saved conversations now supersede that history limit.

Real-model evaluation exposed incorrect numeric recombinations and financial
interpretations. The foundation therefore keeps exact outcomes in server facts
and supplies qualitative context to the explanation model. Schema/citation and
numeric-prose checks are not proofs of semantic correctness; review remains
required. See the contract's evaluation notes and explicit operational limits.

Receipt scanning was initially deferred; after restarting the continuous cycle
the user selected the implementation tracked in DOMAIN-004 above. Forecasting,
and basket optimization remain backlog items. Personalization is implemented
under DOMAIN-005 above. Further assistant capabilities, hosted
use, a new model/provider, external retrieval and spending require their own
scope/operational review; this entry does not activate a continuous feature cycle.

These are documented boundaries, not claims that the user individually selected
each detail or approved a production replacement.

| ID | Current limit and evidence | Status | Follow-up / review trigger |
| --- | --- | --- | --- |
| MVP-008 | Original account foundation recorded pending seller intent only, with verification/role decisions deferred. [Account workflow](../backend/README.md). | Superseded by approved manual-review MVP-017; retain this entry as history of the initial boundary. No automatic decisions or evidence were backfilled. | Production verification standards, evidence, audit/revocation/recovery and onboarding controls remain subject to the follow-up in MVP-017. |
| MVP-009 | USD-only deterministic economics; explicit modeled fees; limited unit conversions and bounded requests/reports. [Economics formulas and limits](fair-price-engine.md). | Implemented. Taxes, shipping, discounts and multi-currency settlement are not modeled in checkout totals. | Before broader commerce: agree tax/shipping/discount rules and supported currencies/units, exact rounding and provider reconciliation. Do not invent fees or exchange rates. |
| MVP-010 | Manually entered unverified market/supplier evidence and deterministic quality checks; external price retrieval and verification deferred. [Engine roadmap](fair-price-engine.md). | Implemented provenance/freshness, Quality Locks, reports and approved Passports. Original no-LLM boundary is superseded only by approved local assistant MVP-021. A passing claim check or publication is not certification or objective fairness. | Review approved sources, verification, freshness and quality equivalence before external integrations/recommendations. New provider spending/infrastructure still require approval. |
| MVP-011 | Sellable-product stock/holds are implemented, but raw-material inventory, production consumption, fulfillment and return restocking are separate. [Order/inventory contract](api-contract.md). | Implemented local commerce foundation. Refunds do not automatically reverse production costs or restock. | Define production and fulfillment workflows and stock reconciliation before coupling these features. Test concurrency, expiry, retries and recovery at the intended usage level. |
| MVP-012 | Backend JSON APIs/examples exist; shared frontend contract acceptance and real browser/end-to-end integration remain pending. [API contract status](api-contract.md). | Backend-tested local implementation; this register does not claim a working frontend or successful provider/browser checkout. | Coordinate frontend acceptance, browser session/CORS/payment behavior and end-to-end checks before calling a user journey complete. |
| MVP-013 | Nearby search uses manually chosen points at most two decimal places, straight-line spherical distance, a 1..500 km radius, and a 1,000-candidate bounding-box limit. [Discovery #26](https://github.com/Firewallwarden/FairMade/pull/26). | Integrated into main by #26. No maps/geocoding service or buyer-location storage. Results do not guarantee travel distance, pickup address, anonymity or stock. A too-broad query errors explicitly rather than returning a truncated nearest-first page. | Improve location entry and spatial search as usage grows; review radius/precision policy and disclosure UX with the frontend. Choose any provider/infrastructure separately. Keep privacy, bounded requests and current publication/authorization checks when replacing this implementation. |

## Confirmed product model decisions

These choices are not temporary local-MVP limits and have no automatic expiry.
Implementation limits and optional enhancements do not imply replacement at a
particular deployment stage.

| ID | Choice and evidence | Current status and limits | Follow-up / review trigger |
| --- | --- | --- | --- |
| DOMAIN-001 | Support livestock groups **and** individual animals together. After #34, the user selected option 3 to enable detailed, precise data. [Contract and examples](livestock-tracking.md). | Implemented and tested in [#35](https://github.com/Firewallwarden/FairMade/pull/35); prerequisite completed-production #33 is verified integrated on main: private profiles, distinct observed headcounts/registered members, revision-safe membership and immutable history, plus explicit frozen group/animal sources on completed reports. Implementation limits include manual observations, exact species-label matching, one current group per animal, one source per report and existing whole output units. No certification or automatic per-animal allocation. | Preserve both tracking levels. Separately decide effective-dated reconstruction, measured multi-source allocations, genealogy/health/feed evidence, taxonomy/imports and reporting. Review retention, backup/restore, capacity/concurrency and frontend integration for hosted use. These are optional extensions or operational reviews, not automatic policy changes or approval for new providers. |
| DOMAIN-002 | Supplier profiles, ratings and reliability history remain private per seller. After #35 opened, the user selected option 1 and requested #28-#35 squash merges before implementation. [Contract](private-supplier-reliability.md). | Implemented and tested in independent [#36](https://github.com/Firewallwarden/FairMade/pull/36), started from main after all eight merges were verified. Private profiles/history, reported ratings/delivery dates, linear corrections and exact known/unknown summary denominators; optional owned quote snapshots. Scores and timing remain unverified, with no automatic Quality Lock, pricing or disclosure effects. | Preserve private visibility unless a new policy is approved. Manual 1..5 scores, date-level timing and one optional source quote are implementation choices, not additional user decisions. Procurement/receipt evidence, partial shipments, richer measures, aliases/imports, useful reports and hosted operations remain separately scoped. Sharing/community ratings is not an automatic production requirement. |

## Confirmed product disclosure decisions

These choices are product policies, not temporary MVP limits. Do not infer that
production deployment requires replacing them.

| ID | Confirmed decision | Implementation/status | Follow-up |
| --- | --- | --- | --- |
| DISC-001 | Publish exact available sellable-unit quantities. User chose option 2 after #33 opened and rejected an MVP/production rationale for restricting counts. [Implementation #34](https://github.com/Firewallwarden/FairMade/pull/34). [Policy and contract](public-listing-availability.md). | Implemented and tested in #34, verified integrated on main: live quantities/status on visible listing cards/details, storefront/nearby searches and favorites; filters precede pagination. Missing, unit-mismatched or inconsistent stock remains unknown; known zero is explicit. This decision has no automatic expiry. | Coordinate frontend rendering, source/checkout notices and snapshot refresh. Existing live-payment/hosted operational work remains separate. Any disclosure-policy change needs a new decision; exact counts themselves are not a temporary compromise. |
| DISC-002 | Require explicit quantity/unit before publishing new or updated listings, retaining existing approved listings. After #36, the user chose option 2 following explanation of seller-form/publication impact. [Contract](standardized-unit-pricing.md), [PR #37](https://github.com/Firewallwarden/FairMade/pull/37). | Implemented and validated (1,098 backend tests) in independent PR #37: incomplete drafts remain saveable, new approvals require a declaration, seller-approved normalized prices are frozen in listing payloads, and legacy snapshots/hashes/visibility remain unchanged. Checkout still charges per selling unit. Frontend acceptance/integration is pending. | This is an ongoing product policy, not an MVP-only restriction. Supported units, six-place display rounding and precision status are implementation limits. Buyer comparisons/ranking, additional units/currencies, evidence verification and hosted operations remain separately scoped. No automatic quantity inference, forced legacy backfill, altered charges or relaxation of Quality Locks is authorized. |

## Rules that remain in force beyond MVP

General accounts default to buyer; seller access is additive and requires the
approved verification process. Seller economics remain private unless explicitly
approved for disclosure. Mandatory Quality Locks, deterministic monetary
calculations, backend authorization and verified payment completion remain
requirements. They are not temporary compromises to remove for production.

## Updating this register

For a new tradeoff, record the confirmed decision or documented limit, its source,
implementation status, consequences, and the trigger/follow-up for revisiting it.
Link the feature PR and update API/feature documentation as appropriate. Retain
superseded entries with a replacement link rather than deleting their rationale.
Review this log before planning hosted deployment, live payments, or a feature
that relies on a listed limitation. New unresolved product choices still require
the user's answer.
