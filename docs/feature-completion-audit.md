# Original feature list: backend completion audit

Snapshot: 2026-11-10, after the user chose verified FairMade sales only for
forecasting and requested the remaining assistant versus wider-product scope.
This maps the original supplied list; it does not authorize new work or change
the optional continuous-cycle rules.

The fetched main baseline is 16bd9c03933b176fc67c325c3a30932ee16e869b.
Assistant PRs #38 through #46 are still open and main-targeted; their code is
implemented in feature branches, not integrated into main. This forecast change
branches from #42 and does not require the receipt/personalization/basket
extensions. Refresh published children after prerequisite squash merges;
merging a stack in order alone is not integration.

Backend availability is distinct from frontend completion, shared contract
acceptance, provider/browser end-to-end checks and a recorded demonstration.
The backend agent has not audited the frontend developer's current branch and
does not claim that every browser feature is missing or complete.

## How much assistant work remains?

The usable assistant foundation is implemented in open PRs: seller/buyer scoped
questions, saved conversations, source rechecks and exact calculated facts;
seller economics, history and supplier explanations; descriptions, receipt
review/questions; buyer confirmed preference memory and activity-informed
suggestions; single-storefront basket plans.

Forecasting is implemented in this change. After it, there are **three grouped
assistant capability areas** still partial or absent from the original expanded
wishlist. These are planning groups, not a claim that only three endpoints or
three small tasks remain:

| Remaining group | Existing coverage | Work still needed |
| --- | --- | --- |
| Seller insights and alerts | Break-even/target-margin warnings, cost/history facts, reviewed spending aggregates and private production/material records exist. | Structured waste/profit-improvement opportunities and low-margin/expense-increase alerts with explicit evidence, baselines and thresholds. Existing warnings/questions are not an alert feed or notification system. |
| Seller and buyer bundle suggestions | Basket planning selects acceptable alternatives at existing prices. | Explainable product pairing/bundle proposals. Basket optimization is not a bundle feature; promotional discounts, repricing and combined checkout need separate decisions. |
| Richer ingredient/material and supplier recommendation assistance | Buyer explanations use approved disclosures; supplier checks show current failures and eligible cost minima. | More complete disclosed ingredient/material explanations and quality/savings/balance recommendation policies. Do not invent composition, certifications, availability or objective quality/value scores. |

Receipt OCR is implemented but the real full image-to-expense smoke test remains
pending local Tesseract setup after the installer was canceled. It is an
integration/setup gap, not a second receipt feature to rebuild. Persistent
memory is implemented within documented owner/scope/retention limits; it is
not unbounded memory across every record or every conversation.

Recommended scope after this forecast PR: move to the missing core marketplace
and purchase capabilities, then complete integration/demo checks. The remaining
expanded assistant wishlist should not obscure a missing core buying flow.
This is a prioritization recommendation, not automatic deferral or cancellation
of any user-requested item.

## Implemented assistant work under review

| Feature | Evidence / status |
| --- | --- |
| Local seller and buyer questions, deterministic facts/citations, private/public source boundaries | [PR #38](https://github.com/Firewallwarden/FairMade/pull/38), open; local Ollama/Qwen3. |
| Seller sales and saved cost-history questions | [PR #39](https://github.com/Firewallwarden/FairMade/pull/39), dependent draft. These are bounded history questions, not validated seasonality. |
| Supplier eligibility and mandatory-quality explanations | [PR #40](https://github.com/Firewallwarden/FairMade/pull/40), dependent draft. No automatic substitute or recipe change. |
| AI product description drafts with explicit seller approval | [PR #41](https://github.com/Firewallwarden/FairMade/pull/41), dependent draft. Public publication remains separate. |
| Saved buyer/seller conversations, restart continuity and erasure/expiry | [PR #42](https://github.com/Firewallwarden/FairMade/pull/42), dependent draft; [contract](assistant-conversations.md). |
| Local receipt OCR/extraction and explicitly reviewed expense records | [PR #43](https://github.com/Firewallwarden/FairMade/pull/43), dependent draft; real full OCR smoke remains pending. |
| Reviewed receipt expense questions | [PR #44](https://github.com/Firewallwarden/FairMade/pull/44), dependent draft; no inferred product-cost allocation. |
| Buyer opt-in personalization, favorites/verified sandbox signals and confirmed memory proposals | [PR #45](https://github.com/Firewallwarden/FairMade/pull/45), dependent draft. |
| Budget-aware single-storefront basket plans and saved explanations | [PR #46](https://github.com/Firewallwarden/FairMade/pull/46), dependent draft. Multi-seller plans are explicitly a later enhancement. |
| Verified-sales unit baseline and inventory planning explanations | Implemented in this change; [source, formulas and limitations](observed-sales-forecast.md). Offline history is a potential later enhancement. |

## Core feature map outside the assistant chat shell

“Present on main” below means the cited backend code/docs are in the fetched
main baseline. It is not a claim of frontend acceptance, live payment readiness,
independently verified seller claims or completion of every possible expansion.

| Original-list area | Backend status | Gap / boundary |
| --- | --- | --- |
| Seller profiles/storefronts; listings, descriptions and photos | Present on main: [storefront API](../backend/src/fairmade/storefronts/routes.py), [listing API](../backend/src/fairmade/marketplace/routes.py), [photo API](../backend/src/fairmade/photos/routes.py). | One storefront/account is the confirmed initial policy; browser integration must be checked with frontend. |
| Recipe/ingredient management | Present on main: [manual recipe contract](manual-recipe-costing.md). | Manual prices/quantities, no live ingredient catalog or automatic supplier substitution/consumption. |
| Livestock production tracking | Present on main: [groups, animals and production source tracking](livestock-tracking.md). | Seller-reported data, no automatic per-animal allocation or certified animal-welfare claim. |
| Material/supply inventory | Present on main: [material inventory](manual-material-inventory.md). | Quantity/event tracking; lot/expiry/valuation and automatic recipe consumption remain deeper optional work. |
| Labor, packaging, utilities, equipment and batch yield/unit costs | Present on main: [economics formulas](fair-price-engine.md), [actual production records](completed-production-records.md). | Manual allocation and observed completed output. A separate equipment asset ledger or production scheduler is not implied by these calculations. |
| Product quality standards and minimum requirements | Present on main: [Quality Lock API](../backend/src/fairmade/quality/routes.py). | Structured rules and immutable evaluations; matching seller claims are not independent verification. |
| True costs, margins/markup, break-even, price scenarios and profit projections | Present on main: [calculator](fair-price-engine.md), saved analyses and pricing reviews. | Outputs depend on seller inputs and modeled fees/yields; AI does not silently choose a price or calculate money. |
| AI-recommended sustainable price choices combining economics, market context and quality | Partial: deterministic seller-target ranges, comparisons, reviews and assistant explanations exist. | A richer recommendation policy that turns all three into proposed price choices is not yet implemented; the current margin-target range is not an objective fairness verdict or an AI-chosen market price. |
| Local comparable finished products and price-change simulations | Present on main: [comparison API](../backend/src/fairmade/comparisons/routes.py), calculator scenarios. | Comparable evidence is manually entered with provenance; no unsupported live-price retrieval. |
| Seasonal and historical cost analysis | Partial: saved cost differences/history questions exist in #39. | Save-time trends do not prove seasonality or actual procurement inflation. A seasonal evidence/model feature remains unimplemented. |
| Unsustainable-price warnings | Present on main: calculator/review warnings; assistant explanations in #38/#39. | Not an autonomous repricing or notification workflow. |
| Supplier/bulk/usable-unit comparisons, specification checks and transport/availability inputs | Present on main: [supplier contract/API](../backend/src/fairmade/suppliers/routes.py). | Seller-entered evidence, freshness and quality exclusions. Automated nearby supplier discovery/live stock is not implemented. |
| Supplier ratings/reliability | Present on main: [private supplier records](private-supplier-reliability.md). | Private seller-reported observations, not shared verified reputation. |
| Quality/savings/balance substitution recommendations and quality-reduction alerts | Partial: eligible-only minima and failure/exclusion explanations exist (#40). | Ranked recommendation modes, ingredient replacement proposals and confirmed application need explicit policy; no failing Quality Lock can become an acceptable saving. |
| Orders, verified sandbox payments, transaction history, stock updates, sales/profit reporting | Present on main: [orders](../backend/src/fairmade/orders/routes.py), [payments](../backend/src/fairmade/payments/routes.py), [seller sales](../backend/src/fairmade/sales/routes.py). | Shared sandbox merchant is approved for development. Seller-connected production merchants and live payouts are explicitly deferred. |
| Refund/cancellation workflows | Present on main: [refund API](../backend/src/fairmade/refunds/routes.py). | Buyer requests require seller review/approval; no automatic restocking. |
| Order/purchase confirmations and order history | Backend order/payment status and history present on main. | Browser confirmation screens must be verified. Email/push confirmations are not implemented and are not authorized by a status response. |
| Buyer search, basic categories, nearby seller discovery, distance/availability filters | Present on main: catalog product-type filters, [nearby discovery](../backend/src/fairmade/discovery/routes.py), [availability](public-listing-availability.md). | Categories are sourdough/eggs/other, not an extensible taxonomy. No live geocoding or driving-distance guarantee. |
| Sort by price, quality and overall value | Incomplete: catalog currently sorts by publication order; filter and comparison primitives exist. | Price sorting and explainable quality/value ordering still need implementation. Unknown/unverified quality must not become an invented universal score. |
| Product comparisons, seller/product information, favorites | Present on main: comparable evidence, public Passports/listings/storefronts and owner favorites. | Frontend comparison pages and saved-product browsing need frontend confirmation. |
| Fair Price Passport, seller-approved costs/material/labor/overhead, disclosed margins | Present on main: [Passport API](../backend/src/fairmade/passports/routes.py). | Omitted fields remain unknown; seller consent governs disclosure. Not every seller must reveal every cost. |
| Standard unit prices, reported/estimated indicators, evidence warnings | Present on main: [standard unit pricing](standardized-unit-pricing.md), provenance and review warnings. | No false independent-verification or objective-fairness guarantee. |
| Buyer AI price/value explanations and alternative recommendations | Foundation plus #45/#46 under review. | Preferences/activity and compatible alternatives only; richer ingredient explanations/overall-value policies remain partial. |
| Cart/order summary, purchase history, PayPal purchase | Backend APIs present on main. | Validate the real browser-to-sandbox journey with frontend and configured sandbox credentials; a provider double is not that integration check. |
| Seller communication | No buyer–seller message API found in the audited backend. | Core gap: decide eligible conversation scope (for example, order-bound versus pre-purchase), privacy, retention and abuse controls before implementation. |
| Reviews and verified-purchase feedback | Present on main: [review contract](product-reviews.md). | Sandbox purchase evidence and unverified buyer opinions; hosted moderation/reporting/appeals remain follow-ups. |

## Suggested next priorities

1. Finish and publish the approved verified-sales forecasting work.
2. Address core buyer–seller communication and the missing marketplace ordering
   behavior, with visible design questions where policy is needed.
3. Complete the remaining pricing/supplier recommendation policy if required
   for the intended signature-feature demonstration; keep quality constraints
   binding and evidence limitations explicit.
4. Integrate and validate the UI/backend journey, migrations, login/logout,
   source changes, provider failures, real receipt OCR and sandbox purchase/refund.
   Review/merge PRs through the guard workflow; merges are not authorized here.
5. Return to the remaining expanded assistant insights/alerts, bundles and richer
   ingredient/supplier explanations as scope and submission needs permit.

Deferred enhancements include offline sales ingestion, multi-seller shopping
plans, additional storefronts and production seller-connected PayPal merchants.
Their presence in the decision log does not make them mandatory before a local
demo and does not authorize them automatically.

Use this audit as a checklist for product decisions and frontend coordination,
not as a percentage-complete estimate. A working backend endpoint, a merged
feature, an accepted browser contract and a successfully demonstrated user
journey are different completion states.
