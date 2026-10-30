# FairMade — Frontend AI Agent Instructions

These instructions supplement `../AGENTS.md`. Follow all shared security, collaboration, and Git worktree rules there.

## Role and Stack

You are helping the **frontend developer**, who is learning frontend development and works in **JetBrains WebStorm**.

Approved frontend stack:
- **React + TypeScript + Vite**
- **Tailwind CSS** for responsive styling
- Browser-side calls to the partner's **Python/FastAPI** backend

Work within `frontend/` unless the user explicitly authorizes a specific shared documentation or configuration change. **Do not modify `backend/`**.

## Product and Design Direction

Create a polished, accessible, responsive marketplace that feels friendly to independent makers while remaining trustworthy as a fintech experience. Preferred look: warm cream, sage green, earthy neutrals, clean typography, clear information hierarchy, and uncluttered data visualizations.

Two primary user journeys:

### Seller
- Seller dashboard and product management
- Product creation, recipe/ingredient inputs, and egg-production inputs
- Labor, packaging, equipment, utilities, and overhead forms
- Pricing analysis, margin simulations, and break-even visualizations
- Local supplier comparisons with price-source dates and availability status
- **Quality Lock** controls for minimum ingredient/material standards
- AI recommendations for savings that **do not** breach Quality Lock
- Product listing publication and sales/order views

### Buyer
- Marketplace browsing, search, filters, and product details
- **Fair Price Passport** with seller-approved production-cost categories, source/verification labels, and quality claims
- Local alternative comparisons that normalize units and distinguish verified facts from estimates
- AI-generated, evidence-grounded price explanations
- PayPal checkout interface, order confirmation, and error handling

For hackathon development, prioritize a complete flow: **seller enters bread/egg production inputs → backend provides price analysis → seller publishes listing → buyer sees Fair Price Passport → buyer completes a PayPal sandbox purchase**.

## Architecture and Implementation

- Prefer small, reusable components and clear directory ownership, e.g. `src/components/`, `src/pages/`, `src/services/`, `src/types/`, `src/data/`.
- Use TypeScript types/interfaces for request and response bodies.
- Centralize HTTP requests in `src/services/` (for example, `api.ts`). Do not scatter hardcoded API URLs or ad hoc request formats across components.
- Follow `../docs/api-contract.md` once agreed. Until then, label endpoint shapes as **proposed** and confirm them with the backend developer.
- Use structured, replaceable mock data while APIs are unavailable; do not present mock output as live payments, verified prices, or actual AI analysis.
- Keep calculations that establish authoritative prices and order totals on the backend. The frontend can show previews, but backend results are authoritative.
- Handle loading, empty, success, validation, and error states. Keep forms keyboard-accessible and mobile-friendly.
- Never put PayPal secret keys, LLM keys, or other backend credentials into frontend code or `VITE_` environment variables. Public client IDs may be exposed only when required by the supported checkout integration.
- Do not assume PayPal payment succeeded until the backend confirms a verified capture.
- Avoid introducing new libraries or making major structural changes without explaining and obtaining approval.

## How to Work with This Developer

1. Before coding, briefly explain the plan and which files you intend to change.
2. Implement **one small feature at a time**. Do not generate the whole application from a broad product-vision prompt.
3. Explain important React/TypeScript ideas in plain English; avoid assuming prior knowledge.
4. When possible, tell the developer how to run and view the change locally in WebStorm.
5. Run the relevant checks (such as `npm run build` and available lint/tests), report the outcome, and do not claim success if a command fails.
6. Follow root standing approval for in-scope staging, commits, normal feature-branch pushes, and PR creation/updates without repeated confirmation. Obtain explicit approval for merges, remote history rewrites, or shared/backend edits outside the requested scope.
7. Do not silently alter backend API expectations; document proposed contract changes and coordinate with the partner.

## Out of Scope Unless Explicitly Requested

- Implementing FastAPI, databases, AI service backends, or payment capture logic
- Live retailer scraping or unsupported claims of real-time local pricing
- Production authentication, full multi-merchant payouts, or additional infrastructure
- Changes to `backend/` or root `AGENTS.md`
