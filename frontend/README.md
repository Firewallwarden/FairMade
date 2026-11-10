# FairMade frontend

React + TypeScript + Vite + Tailwind CSS. A warm botanical marketplace with real account access, a guided seller workspace and a backend-connected buyer order flow.

## Run locally

From `frontend/`, run `npm install`, then `npm run dev`. Open the local URL Vite prints. In Windows PowerShell, use `npm.cmd` if execution policy blocks `npm`.

`npm run build` checks TypeScript and creates production files in `dist/`. `npm run preview` serves the build. `npm run lint` checks code with Oxlint.

`npm test` runs service and contract tests using Node's native TypeScript support (Node 22.18+). Start the API on port 8000 using the backend README; Vite proxies `/api` to it. See [the integration checklist](INTEGRATION.md) for actual verification and remaining dependencies.

## Experiences and local demo boundaries

- The homepage defaults to buyer. Its buyer/seller switch changes the introduction, photography, marketplace content, explanations, and calls to action.
- `/#/account`: real buyer registration, login/logout, seller applications and status. Passwords are 12–128 characters; signup never grants seller access.
- Sessions use memory only, with fixed backend expiry and revocation. Reload requires login. No credentials/tokens are written to browser storage or logs.
- `/#/seller`: private products, saved cost analyses, Quality Lock requirements/claim checks, dated price observations, comparison reports, disclosure previews, approved Passports/listings and stock.
- `/#/market`: real approved listings, search/type/location/stock filters, product details and expandable Passports.
- `/#/orders`: buyer and seller order views; single-product reservation with a backend-calculated subtotal, retained retry key, cancellation and stock release.
- PayPal's sandbox SDK is loaded only when the backend public configuration enables it. Server capture/reconciliation and verified receipts determine payment success. A disabled integration is clearly labeled.
- `/#/pricing`: anonymous stateless calculator; seller-product calculations save a private analysis.
- Only the homepage inspiration cards use illustrative products/prices and stock photography. They are explicitly labeled and never used as checkout data.
- No connected LLM, live market/supplier lookup, shipping/tax calculation or production seller payout is claimed.
- Motion respects the browser's reduced-motion preference. Forms, role choices, navigation, and buttons support keyboard use.

## Organization

- `components/`: shared layout, forms, feedback, Passports and payment interface.
- `pages/`: account, seller/product workflow, marketplace, listing, order and calculator screens.
- `types/`: shared pricing, product and account-role types.
- `mock/`: replaceable illustrative product data.
- `services/`: typed HTTP adapters, runtime response decoders and memory-only session handling.
- `hooks/` and `utils/`: abortable resource loading, action state, form extraction and display helpers.
- `index.css`: Tailwind import, self-hosted fonts, theme, and responsive component styles.
- `public/images/` and `public/fonts/`: local assets and font licenses.

## Backend connection

The frontend owner accepted the existing demo contracts on 2026-11-09. HTTP requests are centralized through `services/api.ts`, with private requests checking session validity and clearing revoked/expired sessions. The homepage buyer/seller switch is a display preference, never an authentication role.

Optionally set `VITE_API_BASE_URL` in a local `.env.local` (default `/api/v1`). Include the API version prefix. Vite variables are public browser configuration: never put credentials or secrets in them. A separate API origin needs FastAPI CORS configuration. The Vite development proxy is not part of the production build; hosting needs approved API routing.

For seller testing, use a separately provisioned administrator and the documented manual-review process in the backend examples. Use separate seller and buyer accounts; self-purchase is rejected. Do not bypass seller approval or put sandbox secrets into frontend configuration.

PayPal follows the [official standard checkout integration](https://developer.paypal.com/studio/checkout/standard/integrate): create and capture through the backend. Credentialed approval/capture remains a separate test from local automated provider doubles.

## Asset credits

Photographs are downloaded from Unsplash under the [Unsplash license](https://unsplash.com/license). They are visual references and do not verify sample product descriptions.

- Bread: https://images.unsplash.com/photo-1509440159596-0249088772ff
- Eggs: https://images.unsplash.com/photo-1518569656558-1f25e69d93d7
- Soap: https://images.unsplash.com/photo-1600857544200-b2f666a9a2ec
- White tulip bouquet: [Roman Kraft on Unsplash](https://unsplash.com/photos/close-up-photography-of-white-petaled-flower-bouquet-on-brown-wooden-table-tw4olON9liM), https://images.unsplash.com/photo-1476293889456-abfb7492a29f

Cormorant Garamond, DM Sans, and La Belle Aurore are self-hosted from Google Fonts. Their SIL Open Font License files are included in `public/fonts/`. Botanical and sprout drawings are inline SVG. The homepage does not request remote fonts or images at runtime.
