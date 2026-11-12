# FairMade frontend

React + TypeScript + Vite + Tailwind CSS, with private seller tools and a buyer marketplace connected to the implemented FastAPI contracts.

## Run locally

Use the [local development guide](../docs/local-development.md) for the persistent runtime outside Git checkouts. Its usual frontend address is http://127.0.0.1:5173 and its API is on port 8000. Develop and run checks in a dedicated feature worktree. A runtime snapshot only includes the commit explicitly installed there.

From a feature worktree's frontend directory:

```powershell
npm.cmd ci
npm.cmd run dev
npm.cmd run build
npm.cmd run lint
npm.cmd test
npm.cmd run test:e2e:check
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Unit tests use native Node TypeScript support (Node 22.18+). The Playwright suite starts its own website and actual backend with an isolated migrated database on ports 5174/8002. It never resets the retained demo database. See [browser setup](e2e/README.md) for Python dependencies, providers and port overrides, and [the acceptance record](e2e/ACCEPTANCE.md) for actual results and limitations. `npm.cmd run test:e2e:report` opens the latest HTML report. `npm.cmd run preview` serves built files; production API routing must be provided separately from Vite's development proxy.

## Where to find features

- Account: register/sign in, seller application/status; administrators can open seller-application review.
- Seller workspace: products, materials, livestock, private supplier records, receipts/expenses and itemized sales.
- Product workspace: deterministic analysis, recipes/costings, completed production, Quality Locks and historical evaluations, observations/comparisons, supplier quotes/savings, complete pricing reviews, business reports and publication.
- Photos & description: private image uploads and local-model description drafts that require seller review. Review & publish: editable saved Passports, disclosures, fresh previews, publication/withdrawal, stock and listings.
- The market / Meet the makers: approved products/storefronts, filters and radius discovery. Product details expose approved Passports, comparisons, favorites, purchase previews and the buyer assistant.
- Ask FairMade: saved buyer/seller conversations, follow-ups, explicit private-source selection and history. Seller product pages link to the seller assistant.
- Orders: buyer purchases and refund requests, seller orders and refund inbox, participant messages, unpaid cancellation, pickup/history and existing refund decision/reconciliation controls.
- Preferences and planning: explicit optional personalization, basket optimization and buyer/seller pair suggestions.
- Pricing: anonymous stateless calculator; product calculations save private analyses.

The [integration map](INTEGRATION.md) and [demo checklist](DEMO-CHECKLIST.md) provide the full navigation and review handoff. Older selectors/history have paginated access and preserve explicit selections. Unknown costs, fees and evidence stay unknown.

## Backend and provider boundaries

HTTP adapters and response validation live in `src/services/`. The [shared API contract](../docs/api-contract.md) defines the implemented endpoints. Backend authorization, revision checks, deterministic money calculations and payment verification remain authoritative. The homepage buyer/seller switch changes presentation only.

Sessions stay in memory; reload requires login. Revoked/expired sessions clear private access. Use separate seller and buyer accounts and the documented administrator-review process; self-purchase is rejected.

Ollama qwen3:8b powers the enabled local assistant and copy workflows through the backend. Running service/configuration and available sources determine availability. Receipt extraction additionally needs Tesseract/English and reviewed real-image acceptance. There is no automatic cloud fallback, live supplier scraping or unsupported fairness verdict.

PayPal loads only when backend configuration enables its sandbox integration. Create/capture/reconciliation run on the backend. Payment and refund completion require verified backend status; an approval click is insufficient. Credentialed browser tests remain separate from provider-disabled checks. See the acceptance record for checks completed against this frontend.

`VITE_API_BASE_URL` optionally selects the public API base (default `/api/v1`). Vite variables enter browser bundles: never put credentials or server secrets in them. A separate API origin requires approved CORS configuration. Keep PayPal secrets, receipt fixtures and private provider settings outside Git.

The HTML metadata `fairmade-source-revision` and `fairmade-source-state` identify the served checkout. After committing/pushing, rebuild/restart and verify the revision matches the published head (or deployed main). A checkout reports clean; an identified exported runtime reports exported-snapshot. Exported snapshots can supply their exact source through server-side `FAIRMADE_SOURCE_REVISION`; unknown sources remain labeled unknown.

Only homepage inspiration cards use labeled illustrative products/prices and stock photography. They do not become checkout evidence. Keyboard and narrow-screen checks are part of the browser suite; these do not constitute a full accessibility audit.

## Organization

- `src/components/`, `src/pages/`: shared UI and feature workspaces.
- `src/services/`, `src/types/`: HTTP contracts, decoders and memory-only sessions.
- `src/hooks/`, `src/utils/`: resource/action state, forms and presentation helpers.
- `src/mock/`: labeled illustrative homepage data.
- `public/images/`, `public/fonts/`: local assets and licenses.
- `e2e/`: real-browser workflows, isolated server setup and acceptance evidence.

## Asset credits

Photographs are downloaded from Unsplash under the [Unsplash license](https://unsplash.com/license). They are visual references and do not verify sample product descriptions.

- Bread: https://images.unsplash.com/photo-1509440159596-0249088772ff
- Eggs: https://images.unsplash.com/photo-1518569656558-1f25e69d93d7
- Soap: https://images.unsplash.com/photo-1600857544200-b2f666a9a2ec
- White tulip bouquet: [Roman Kraft on Unsplash](https://unsplash.com/photos/close-up-photography-of-white-petaled-flower-bouquet-on-brown-wooden-table-tw4olON9liM), https://images.unsplash.com/photo-1476293889456-abfb7492a29f

Cormorant Garamond, DM Sans, and La Belle Aurore are self-hosted from Google Fonts. Their SIL Open Font License files are included in `public/fonts/`. Botanical and sprout drawings are inline SVG. The homepage does not request remote fonts or images at runtime.
