# FairMade frontend

React + TypeScript + Vite + Tailwind CSS. A farmers-market homepage with distinct buyer and seller experiences, a frontend signup preview, and a backend-connected production-cost calculator.

## Run locally

From `frontend/`, run `npm install`, then `npm run dev`. Open the local URL Vite prints. In Windows PowerShell, use `npm.cmd` if execution policy blocks `npm`.

`npm run build` checks TypeScript and creates production files in `dist/`. `npm run preview` serves the build. `npm run lint` checks code with Oxlint.

`npm test` runs service and pricing-contract tests using Node's native TypeScript support (Node 22.18+). Select **Cost calculator** in the navigation or visit `/#/pricing`. Start the API on port 8000 using the backend README; Vite proxies `/api` to it. See [the integration checklist](INTEGRATION.md) for capabilities and remaining dependencies.

## Experiences and preview boundaries

- The homepage defaults to buyer. Its buyer/seller switch changes the introduction, photography, marketplace content, explanations, and calls to action.
- Switching the homepage also preselects that account type and clears form details, errors, and completion notices. Changing the signup choice does not change the homepage.
- Header and in-page account links scroll to the signup section. The mobile menu includes account access.
- Signup is explicitly a preview. Use invented details. Name and email are required; the preview password must be at least eight characters and match its confirmation.
- Invalid submission shows inline errors and focuses the first invalid field. Password visibility is optional. Valid submission clears the fields and explains that no account was created.
- Signup uses temporary component state only. There are no account API requests, credential logs, cookies, or browser-storage writes. No authentication or payment integration is implemented.
- Products, seller descriptions, and USD prices are illustrative. They do not represent verified goods, real local availability, or authoritative price recommendations.
- Motion respects the browser's reduced-motion preference. Forms, role choices, navigation, and buttons support keyboard use.

## Organization

- `components/`: header, branding, botanical artwork, role switch, product cards, and signup preview.
- `pages/`: page layouts, currently `LandingPage.tsx`.
- `types/`: shared frontend product and account-role types.
- `mock/`: replaceable illustrative product data.
- `services/`: product data access and the central HTTP helper.
- `index.css`: Tailwind import, self-hosted fonts, theme, and responsive component styles.
- `public/images/` and `public/fonts/`: local assets and font licenses.

## Future backend connection

The page reads sample products through `services/products.ts`. Integrate only after reviewing and agreeing on `../docs/api-contract.md`; centralize requests through `services/api.ts`. The preview's buyer/seller choice is a UI preference, not a proposed backend account or authentication payload.

Optionally set `VITE_API_BASE_URL` in a local `.env.local` (default `/api/v1`). Include the API version prefix. Vite variables are public browser configuration: never put credentials or secrets in them. A separate API origin needs FastAPI CORS configuration. The Vite development proxy is not part of the production build; hosting needs approved API routing.

Do not turn the preview into working registration without coordinating authentication, seller eligibility, error handling, and session behavior with the backend developer.

## Asset credits

Photographs are downloaded from Unsplash under the [Unsplash license](https://unsplash.com/license). They are visual references and do not verify sample product descriptions.

- Bread: https://images.unsplash.com/photo-1509440159596-0249088772ff
- Eggs: https://images.unsplash.com/photo-1518569656558-1f25e69d93d7
- Soap: https://images.unsplash.com/photo-1600857544200-b2f666a9a2ec
- White tulip bouquet: [Roman Kraft on Unsplash](https://unsplash.com/photos/close-up-photography-of-white-petaled-flower-bouquet-on-brown-wooden-table-tw4olON9liM), https://images.unsplash.com/photo-1476293889456-abfb7492a29f

Cormorant Garamond, DM Sans, and La Belle Aurore are self-hosted from Google Fonts. Their SIL Open Font License files are included in `public/fonts/`. Botanical and sprout drawings are inline SVG. The homepage does not request remote fonts or images at runtime.
