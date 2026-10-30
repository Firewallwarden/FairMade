# FairMade — Backend AI Agent Instructions

These instructions supplement `../AGENTS.md`. Follow all shared security, collaboration, and Git worktree rules there.

## Role and Stack

You are helping the **backend developer**, who works in **JetBrains PyCharm**.

Primary backend stack:
- **Python + FastAPI** for HTTP APIs
- Pydantic models for request/response validation
- A relational database and appropriate persistence layer (confirm the specific database and ORM before making architectural choices)
- An approved AI provider for extraction, recommendations, and explanations
- **PayPal sandbox APIs** for checkout order creation and capture

Work within `backend/` unless the user explicitly authorizes a specific change to shared API documentation. **Do not implement or edit frontend interfaces in `frontend/`**.

## Responsibilities

- Design and implement documented JSON endpoints for marketplace products, seller listings, pricing analysis, comparisons, explanations, orders, and seller reporting.
- Maintain API request/response schemas, validation, predictable errors, and documentation suitable for integration with React.
- Build deterministic and testable production-cost calculations for at least **sourdough bread** and **egg production** during the hackathon MVP.
- Account for materials/ingredients, batch yields or egg production volume, labor, equipment, utilities, packaging, overhead, and applicable transaction fees where modeled.
- Analyze profitability, sustainable target margins, and scenarios without assuming that charging more or using cheaper ingredients is automatically better.
- Support **Quality Lock** constraints. Reject or clearly exclude substitutions that fail mandatory standards, including safety, product specifications, or animal welfare where applicable.
- Store supplier price provenance (source, location, date, unit, and whether the value is verified, seller-reported, or an estimate). Normalize costs before comparing alternatives.
- Produce buyer-facing **Fair Price Passport** data respecting seller disclosure choices; do not leak private cost detail without authorization.
- Orchestrate AI for ingredient extraction, identifying missing cost categories, recommendations, and plain-language explanations based on validated facts.
- Implement PayPal sandbox order creation/capture, status tracking, order persistence, and inventory updates on verified successful captures.

## API Contract and Frontend Integration

- Coordinate with the frontend developer using `../docs/api-contract.md` once it is agreed.
- Define endpoint method/path, request schema, response schema, IDs, currency and money representation, units, required/optional fields, authentication assumptions, and standard errors.
- FastAPI's generated OpenAPI documentation should accurately describe implemented endpoints; proposed routes are not live until built and tested.
- Notify the frontend developer before making breaking schema changes; favor additive, backward-compatible revisions.
- Provide realistic **clearly labeled sample JSON** for frontend mock data and integration tests.
- Configure CORS appropriately for the approved development and deployed frontend origins; do not enable indiscriminate permissive CORS in production.

## Security, Accuracy, and Payment Handling

- Keep secrets in server-side environment variables or an approved secrets manager; never commit credentials or print sensitive payment data to logs.
- Calculate purchase amounts on the backend from authoritative product/order records. Do not trust client-submitted monetary totals.
- Use approved PayPal APIs and sandbox accounts for development. Verify capture results server-side, avoid duplicate order processing, and handle failure/retry paths safely.
- Use exact decimal or integer-minor-unit arithmetic for money, consistent with the approved contract. Test margins, per-unit costs, rounding, and unit conversion.
- Validate inputs and permissions. A seller should not access or edit another seller's private data without authorization.
- Do not let an LLM fabricate prices, supplier stock, qualifications, or cost facts. Provide sources/dates and distinguish verified from estimated claims.
- Never silently relax seller-defined Quality Lock constraints to improve margins.
- Do not add paid APIs, scraping services, third-party infrastructure, or major architecture changes without approval.

## Workflow and Validation

1. Inspect existing backend code, root instructions, and the shared API contract before modifying anything.
2. Propose a focused change and list intended files and endpoint impacts.
3. Implement in the assigned feature worktree and branch, following the root Git workflow.
4. Add or update relevant automated tests, including invalid-input and failure cases.
5. Run available formatting, linting, tests, and API checks; summarize outcomes and limitations.
6. Explain new/changed endpoints with request and response examples for frontend integration.
7. Follow root standing approval for in-scope staging, commits, normal feature-branch pushes, and PR creation/updates without repeated confirmation. Obtain explicit approval for merges, remote history rewrites, or shared/frontend edits outside the requested scope.

## Out of Scope Unless Explicitly Requested

- Implementing React components, UI styling, or frontend page behavior
- A full multi-seller payments/payouts platform beyond the approved sandbox demonstration
- Unsupported automatic retrieval of live local prices
- Changing root `AGENTS.md` or frontend instructions without coordination
