# Frontend demo expansion

The user requested all feasible frontend improvements on 2026-11-11.
Priorities retain the chosen cream/sage design and primary seller-to-buyer demo.

- [x] Existing accounts, seller costs/quality/publication, market and unpaid orders.
- [x] Inspected additive backend contracts; no backend implementation changes.
- [x] Saved local assistant UI: facts/prose/evidence, explicit source selection,
  history pagination, retry IDs, expiry and deletion controls.
- [ ] Validate the assistant with real backend/model and failure paths.
- [ ] Photos, storefronts and nearby presentation.
- [ ] Messaging, pickup, seller-approved refunds and buyer reviews.
- [ ] Favorites, evidence-based ordering and comparison tools.
- [ ] Prioritized supplier/business tools that support the demo.
- [ ] Final responsive/keyboard/error checks and walkthrough.

Dependencies: real PayPal approval/capture needs server-only sandbox setup;
local AI needs the existing Ollama/Qwen3 service enabled; actual receipt-image
OCR needs Tesseract. No mocked processing will be presented as real.

Shared contract/MVP documentation updates require explicit approval: automatic
approval review rejected the requested shared edits as outside the current
frontend-only scope. The existing backend shapes are being checked against
their published proposals; formal shared acceptance/status updates remain pending.

Branches depend on the existing frontend demo until it is integrated into main.
No main merge or production deployment is authorized.
