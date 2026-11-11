# Original feature list: backend completion audit

Snapshot: 2026-11-11. This replaces the earlier forecast-only audit after the
authorized continuous cycle. Recommended local MVP designs were delegated by
the user; deeper alternatives are recorded with their feature PRs.

The earlier baseline was `16bd9c03933b176fc67c325c3a30932ee16e869b`.
PRs #38 through #56 have now been reviewed, squash-merged into main and verified
there. Published children were refreshed after prerequisite merges. The resulting
application matches the combined validation snapshot; this final handoff (#57)
records the review and retains its reproducible integration checks.

The remaining work is browser/provider integration and demonstration, plus explicitly
bounded deeper functionality below. It would be inaccurate to call the full
original wishlist or a production marketplace finished. Backend APIs, accepted
browser contracts, frontend screens and successful real-provider demos are
different completion states. The frontend developer's current branch has not
been audited here.

## Integrated seller and buyer assistants

| Capability | Published backend implementation | Boundary / later depth |
| --- | --- | --- |
| Seller/buyer questions with exact facts and cited qualitative answers | [#38](https://github.com/Firewallwarden/FairMade/pull/38) | Free local Ollama/Qwen3; no cloud fallback or autonomous changes. |
| Sales and saved cost-history questions | [#39](https://github.com/Firewallwarden/FairMade/pull/39) | Bounded nominal histories; not actual-cost accounting. |
| Current supplier exclusions and Quality Lock explanations | [#40](https://github.com/Firewallwarden/FairMade/pull/40) | Ineligible alternatives cannot be acceptable savings. |
| AI description drafts | [#41](https://github.com/Firewallwarden/FairMade/pull/41) | Seller reviews exact private copy; public publication is separate. |
| Persistent buyer/seller conversations | [#42](https://github.com/Firewallwarden/FairMade/pull/42), [contract](assistant-conversations.md) | Owner/scope-bound, bounded history, restart continuity, source refresh, deletion and thirty-day inactivity expiry. Not unlimited memory across all records. |
| Receipt OCR and reviewed expenses | [#43](https://github.com/Firewallwarden/FairMade/pull/43) | Transient images, local Tesseract/Qwen drafts, explicit seller approval; real full image OCR remains pending setup. |
| Reviewed receipt expense questions | [#44](https://github.com/Firewallwarden/FairMade/pull/44) | Seller-wide totals, no implicit allocation or double deduction from modeled profits. |
| Buyer personalization and remembered preferences | [#45](https://github.com/Firewallwarden/FairMade/pull/45) | Opt-in favorites/verified sandbox purchase signals; proposed memory updates require confirmation. No inferred sensitive traits. |
| Budget-aware basket optimization | [#46](https://github.com/Firewallwarden/FairMade/pull/46) | Fixed quantities, explicit compatible alternatives, one storefront, exact merchandise subtotal; no reservation/order. |
| Sales baseline and inventory planning | [#47](https://github.com/Firewallwarden/FairMade/pull/47), [contract](observed-sales-forecast.md) | Backend-verified sandbox sales, closed UTC dates, sparse-history nulls; conditional rate projection, not validated demand. |
| Seller waste/profit insights and alerts | [#50](https://github.com/Firewallwarden/FairMade/pull/50) | On-demand margin/cost/expense/output/waste reports. No scheduler, notification feed, causal savings guarantee or automatic business change. |
| Buyer and seller bundles | [#51](https://github.com/Firewallwarden/FairMade/pull/51) | Same-storefront product pairs at existing prices. Consented buyer signals; seller co-purchase counts stay private. No discount, bundle SKU or verified complementarity. |
| Quality/savings/balance supplier recommendations | [#52](https://github.com/Firewallwarden/FairMade/pull/52) | Current hard exclusions first; exact cost and optional known preference matches. Sourcing-input review does not establish a compatible finished-product substitution. |
| Ingredient/material explanations | [#53](https://github.com/Firewallwarden/FairMade/pull/53) | Explicitly approved seller composition declarations for buyers; private recipe input opt-in for sellers. No inferred allergens, safety, nutrition or certification. |
| Conditional price recommendations | [#54](https://github.com/Firewallwarden/FairMade/pull/54) | Selected economics/market review, current quality gates, supported positive-cent review bounds. Unsupported/nonoverlapping evidence can yield no recommendation. |
| Saved cost calendar and annual comparisons | [#55](https://github.com/Firewallwarden/FairMade/pull/55) | Closed save-month snapshots and same-month annual differences; missing data stays unknown. Seasonality is explicitly not established. |
| Consistent economics across combined seller reports | [#56](https://github.com/Firewallwarden/FairMade/pull/56) | Price advice and insights share the selected analysis, including saved follow-ups after restart. |

The three assistant groups listed as missing in the previous audit now have
integrated local MVP implementations (#50–#53). Price advice and descriptive
annual cost analysis have also been added (#54–#55). Further assistant depth
requires better evidence and the follow-ups in the decision log, rather than
another copy of the foundation.

## Original core feature map

“Main” means code/docs exist in the fetched baseline, not a completed browser
journey, verified seller claims or production readiness.

| Original area | Backend coverage | Remaining boundary |
| --- | --- | --- |
| Seller profiles/storefronts; product descriptions/photos | Main: [storefronts](../backend/src/fairmade/storefronts/routes.py), [listings](../backend/src/fairmade/marketplace/routes.py), [photos](../backend/src/fairmade/photos/routes.py). | One storefront/account; browser acceptance/integration. |
| Recipes/ingredients, livestock, materials/supplies | Main: [recipes](manual-recipe-costing.md), [livestock](livestock-tracking.md), [materials](manual-material-inventory.md). | Manual seller reports/prices; no automatic supplier substitution, lot valuation or recipe consumption. |
| Labor, packaging, utilities, equipment, yields/unit costs | Main: [economics](fair-price-engine.md), [completed production](completed-production-records.md). | Manual allocation; no equipment asset ledger or scheduler implied. |
| Quality standards and ingredient requirements | Main: [Quality Locks](../backend/src/fairmade/quality/routes.py). | Structured rules and immutable evaluations; seller claims are not independent certification. |
| True modeled costs, margins/markup, break-even, profit projections and price simulations | Main: deterministic economics and saved reviews; explanations #38–#39, conditional advice #54. | No invented missing costs, automatic price selection or objectively fair-price guarantee. |
| Local finished-product comparisons | Main: [comparisons](../backend/src/fairmade/comparisons/routes.py). | Seller-entered dated observations, not automated verified local market coverage. |
| Seasonal/historical cost analysis | History #39; descriptive calendar/annual analysis #55. | Validated seasonality and actual procurement inflation remain unimplemented. Save timestamps are not expense dates. |
| Unsustainable-price warnings | Main calculator/review warnings; #50 on-demand insight alerts. | No proactive notifications or autonomous repricing. |
| Nearby supplier, bulk, usable-unit, specification, transport/availability comparisons | Main: [supplier API](../backend/src/fairmade/suppliers/routes.py). | Recorded provenance/location/availability; no automated nearby discovery or live stock retrieval. |
| Supplier ratings/reliability | Main: [private records](private-supplier-reliability.md). | Seller-reported private observations; no verified shared reputation. |
| Supplier recommendation modes and quality-reduction warnings | Main exclusions/minima plus #40/#52. | No reviewed ingredient replacement/application workflow or verified product-impact calculation. |
| Orders, PayPal, transactions, inventory updates and fee-aware sales/profit reports | Main: [orders](../backend/src/fairmade/orders/routes.py), [payments](../backend/src/fairmade/payments/routes.py), [sales](../backend/src/fairmade/sales/routes.py). | Shared development sandbox merchant; credentialed browser purchase/capture still needs a smoke test. Production seller merchants/payouts deferred. |
| Refunds/cancellations | Main: [refunds](../backend/src/fairmade/refunds/routes.py). | Buyer request requires seller approval; no automatic restocking. |
| Order/purchase confirmations and history | Main order/payment status/history APIs. | Browser confirmation screens need verification. Email/push confirmations are not implemented. |
| Search/categories, nearby discovery, distance/availability filters | Main: product-type search, [discovery](../backend/src/fairmade/discovery/routes.py), [availability](public-listing-availability.md). | Three basic product types; no live geocoding or driving-distance guarantee. |
| Price, quality, unit-price and value ordering | [#49](https://github.com/Firewallwarden/FairMade/pull/49), independent of assistants. | Explicit public-evidence order and unknown groups; no universal quality/value score or buyer-weighted ranking. |
| Product comparisons, seller/product information, favorites | Main public Passports/listings/storefronts and owned favorites. | Browser comparison/saved-product pages require frontend verification. |
| Fair Price Passport and cost/margin disclosures | Main: [Passports](../backend/src/fairmade/passports/routes.py); explicit composition adds #53. | Exact seller approval governs disclosure; omitted facts stay unknown. |
| Unit pricing, verified/estimated labels and missing-data warnings | Main: [unit pricing](standardized-unit-pricing.md) and provenance. | No fabricated independent verification or fairness verdict. |
| Personalized/budget/quality-price shopping, alternatives, bundles and value questions | #38/#42/#45/#46/#49/#51/#53. | Explicit compatible alternatives and approved evidence; no inferred safety or multi-seller basket. |
| Cart/order summary, history and purchase confirmations | Main backend APIs. | Real browser-to-sandbox walkthrough remains a required integration check. |
| Seller communication | [#48](https://github.com/Firewallwarden/FairMade/pull/48). | Private order-bound messages; pre-purchase inquiries, inbox/notifications and moderation depth deferred. |
| Reviews and verified-purchase feedback | Main: [reviews](product-reviews.md). | Sandbox purchase evidence and buyer opinions; hosted moderation/reporting/appeals remain follow-ups. |

## What remains before the demo

1. Use the integrated checkout and confirm local configuration and demo data.
   The pending implementation PRs have been reviewed and squash-integrated with
   parent refreshes and integration guards; future dependent work needs the same care.
2. Coordinate the browser assistant: create/select conversations, restore paged
   turns after reload, handle revision/retry/expiry/delete, display exact facts
   separately from cited AI prose, and offer confirmed preference controls.
   Frontend owns this work; its actual completion must be checked there.
3. Walk through seller publication, buyer discovery/comparison/Passport,
   purchase/capture, stock, messaging, seller-approved refund and history with
   synthetic data and real sandbox credentials. A provider double is not this check.
4. Configure local Tesseract and run a real image-to-reviewed-expense test before
   advertising receipt scanning as demo-ready. Do not silently substitute mocked OCR.
5. Record the video from an integrated, smoke-tested checkout, showing evidence
   labels, missing-data behavior and safe failures rather than claiming verified
   demand, seasonality, costs, certifications or universal fairness.

See [the backend review/demo handoff](backend-demo-handoff.md) for dependencies,
combined validation evidence and the browser-facing sequence.

Deeper alternatives include validated seasonal/demand models, offline sales
imports, actual-cost reconciliation, multi-seller shopping, configurable bundles,
proactive notifications, source-backed ingredient verification, automatic live
supplier discovery and production seller-connected merchants. Feature PRs retain
their decision-log entries. These remain limits or optional later enhancements,
not authorization for new services, spending or infrastructure.
