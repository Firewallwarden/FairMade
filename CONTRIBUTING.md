# Contributing to FairMade

These guidelines apply to people and coding agents working on both applications.
Read [AGENTS.md](AGENTS.md) and the applicable
[backend](backend/AGENTS.md) or [frontend](frontend/AGENTS.md) instructions before
planning or editing, including after switching worktrees. Follow explicit user
scope and approval instructions. Update this guide as the team agrees on new
conventions; keep examples and commands aligned with the checked-out code.

## Scope and ownership

Backend contributors own Python/FastAPI APIs, business rules, data persistence,
AI orchestration, and payment verification. Frontend contributors own
React/TypeScript interfaces, accessibility, and browser integration. Read across
the boundary for context; obtain explicit permission before editing the other
application. Shared documentation and API contracts require coordination.

Agree on HTTP methods, paths, authentication, errors, fields, units, money
representation, and response shapes in [docs/api-contract.md](docs/api-contract.md)
before integration relies on them. Distinguish implemented endpoints from
proposals and frontend mock data. Favor additive changes; obtain agreement for
breaking changes.

## Feature and pull request workflow

1. Keep the primary worktree for local `main` maintenance. Fetch remote changes
   there and use `git pull --ff-only`; develop and test in a dedicated branch
   and worktree outside it.
2. Start independent work from `origin/main`. A dependent feature may start
   from an unmerged parent feature branch in its own worktree. Every PR must target
   main, including dependent drafts. Never target a feature branch. Identify
   prerequisites and any prerequisite changes included in the cumulative diff.
3. Explain the focused scope and material design choices. Ask for missing product
   decisions; do not introduce paid services, new infrastructure, or major
   architectural changes without approval.
4. Implement and validate in the feature worktree. Before opening or updating its
   PR, fetch and synchronize with current main, or the development parent while
   its prerequisite remains unmerged. Rebase unpublished work; normally merge
   the updated development base into published feature branches and push normally.
   This preserves published history without force-pushes. Review both sides of
   conflicts and coordinate independent edits. The PR destination remains main.
   After each parent squash merge, the agent must refresh the child against
   fetched main and inspect its diff for only the remaining work before asking
   the user to review or merge it. Merging a stack in order alone is insufficient.
   Before marking a PR ready, run
   `scripts/Test-PullRequestReadiness.ps1 -PullRequest <number> -Mode Review`
   from its clean feature worktree. Promote dependent work only after the parent
   merge is verified on fetched main and the child has been synchronized and
   revalidated. For unpublished children, replay only child commits onto main,
   for example with `git rebase --onto origin/main <old-parent-tip>`.
   If safe synchronization requires an unauthorized remote rewrite, create a
   new main-based replacement branch/PR with only the remaining changes; keep the
   old PR draft and identify its replacement.
5. Use descriptive commits. The standing authorization covers in-scope staging,
   commits, normal pushes to the feature branch, and PR creation/updates.
   PR merges into main, direct pushes to `main`, out-of-scope edits, and
   rewriting published history require explicit permission. Never force-push
   `main`; a feature-branch
   `--force-with-lease` also needs explicit authorization.

Describe the problem and resulting behavior in each PR. Include relevant API and
migration changes, validation results, known limitations, and stacked dependencies.
Keep features independently reviewable. Squash merges are preferred once approved.
After merging, run the guard with `-Mode Integrated` to verify the merge commit
is on main. A PR merged into another feature branch is not sufficient. See the
[incident report and guard usage](docs/stacked-pr-integration.md).

## Optional continuous feature cycle

The continuous feature workflow in [AGENTS.md](AGENTS.md#optional-continuous-feature-workflow)
is **opt-in and disabled by default**. Execute it only when the user explicitly
requests it; documenting the workflow or requesting one feature does not enable
automatic selection of further features.

When enabled, select remaining work from the user's supplied feature list by
priority, need and dependencies. Implement, validate, commit, push and open one
PR per feature, then proceed to the next without waiting for merges. Keep
dependent PRs draft and follow the main-targeting and synchronization rules above.
Ask for material product/design decisions, respect pauses and the authorized
scope/duration, and reach out when the list is exhausted or all remaining work
is already under review. The cycle does not expand standing approval or ownership.

## Decision questions and prompt delivery

Ask decision questions in ordinary chat with concise numbered options and a
recommendation when useful. A structured choice popup is an optional additional
channel. Always include the complete question and choices in the visible response
when waiting for the user's answer, so they can reply directly in chat.

A tool's `accepted` result does not prove that a popup appeared or was answered.
Silence, timeouts and preselected choices are not consent or refusal. Wait for
an actual response before work requiring that decision or approval. If a prompt
is missing, restate the question in chat rather than relying on another popup
alone. Apply existing authorization without asking the same permission again.

## Design and readability

Track temporary local-development choices in the
[local MVP decision log](docs/local-mvp-decisions.md). Add or update the relevant
entry with each feature PR: identify confirmed choices versus implementation
limits, link supporting code/docs or PRs, state whether behavior is planned or
implemented, and explain what needs review or improvement beyond local MVP.
When replacing a tradeoff, retain its history and link the replacement. Do not
describe permanent domain rules as temporary or treat a follow-up as approval
to implement it.

Use small, cohesive modules and explicit interfaces. Keep UI, HTTP adapters,
business rules, persistence, and external integrations separate where useful.
Share stable services or domain functions rather than another feature's route
handlers. Avoid circular dependencies, duplicated business rules, and speculative
abstractions.

Choose descriptive names, focused functions, and straightforward control flow.
Comments should explain intent, invariants, or tradeoffs. Bound inputs and
collection responses; consider pagination, queries, indexes, and transaction
boundaries as data grows. Refactor within the task rather than rewriting unrelated
code. Existing formatter/linter configuration takes precedence over generic style
preferences.

## Security throughout design and implementation

Consider who can perform each action, what data crosses each boundary, and how a
request can fail or be repeated. Apply controls proportionate to the feature.
These are contribution standards, not a claim of production security readiness.

- Enforce authorization and ownership on the backend for every protected action.
  Default to denied access and minimal privileges. A hidden UI control, a UUID,
  or a client-supplied role is not authorization. Test cross-account access and
  appropriate unauthenticated/unauthorized failures.
- Validate types, lengths, ranges, allowed fields, and state transitions at trust
  boundaries. Use parameterized database operations. If a feature fetches external
  URLs, constrain destinations and resource use rather than trusting arbitrary
  user-provided URLs. Return safe errors without internal exception details.
- Keep private fields out of public DTOs through explicit allowlists. Preserve
  seller disclosure consent; do not forward raw private records to public APIs,
  browser logs, or AI providers without an approved need.
- Never commit secrets or real payment data. Use server-side configuration and
  synthetic examples. Treat `VITE_` variables as public bundle content. Exclude
  passwords, bearer tokens, authorization headers, sensitive costs, and payment
  data from logs, error reports, screenshots, URLs, and PR descriptions.
- Preserve the approved revocable 24-hour bearer-token lifecycle. Handle expiration
  and logout; do not silently extend sessions. Document browser token handling
  and its risks. Any cookie-authentication change must consider CSRF and secure
  cookie settings. Configure exact CORS origins; CORS does not replace access checks.
- Render untrusted content as text through safe framework APIs. Avoid raw HTML,
  `dangerouslySetInnerHTML`, `eval`, or unsafe URL schemes. If HTML rendering is
  required, use a reviewed sanitization approach and tests.
- Use HTTPS when hosted. Review dependency necessity, provenance, and known
  vulnerabilities when adding/updating packages; maintain any established lockfile.
  Do not disable security checks or broaden permissions to make a feature pass.
- For state-changing or payment operations, consider stale requests, retries,
  concurrent writes, rollback, and duplicate side effects. Keep payment totals
  authoritative on the server and use PayPal sandbox until an approved production
  integration exists. Confirm payment only after backend verification.

For a suspected vulnerability, use the repository's private reporting channel if
available; otherwise contact the maintainer privately through an established
channel. Do not publish exploitable details or credentials in public issues.
Disclose security limitations to reviewers without claiming unperformed audits.
These practices draw on
[OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html),
[REST security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html),
[session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
and [DOM XSS prevention](https://cheatsheetseries.owasp.org/cheatsheets/DOM_based_XSS_Prevention_Cheat_Sheet.html).

## Backend standards

- Use Python 3.11+ and the project's configured interpreter/environment. With
  PyCharm tools, resolve that environment before running the Python toolchain.
- Follow [PEP 8](https://peps.python.org/pep-0008/) naming and readability
  conventions: `snake_case` modules/functions/variables, `PascalCase` classes,
  and `UPPER_CASE` constants. The configured Ruff line length is 100.
- Add useful type annotations at module and service boundaries. Use Pydantic
  models for HTTP validation and explicit response schemas, with the documented
  standard error format. Avoid broad exception catches that hide programming errors.
- Keep deterministic domain calculations independent of HTTP and storage where
  practical. Use Decimal or integer minor units for authoritative money; document
  rounding and units. Do not use binary floats or AI-generated monetary totals.
- Make schema changes through Alembic migrations. Review data preservation,
  constraints, rollback behavior, and deployment assumptions. Do not create or
  modify schemas implicitly on application startup.
- Test meaningful behavior and failure paths using pytest and synthetic data:
  domain edge cases, permissions, privacy, revisions, retries, and transactions as
  relevant. Isolate test databases and avoid live provider calls.

See [backend/README.md](backend/README.md) for setup and examples. From a feature
worktree root, with its environment activated and backend installed:

```powershell
python -m pytest -c backend/pyproject.toml backend/tests
python -m ruff check backend
python -m ruff format --check backend
```

Use the resolved environment executable instead of bare `python` when an IDE
tool provides it. For migration changes, also check upgrade/downgrade behavior,
existing-data preservation, and Alembic metadata consistency against an isolated
test database.

## Frontend standards

- Use the approved React, TypeScript, Vite, and Tailwind stack. Follow the
  checked-out formatter, lint, TypeScript, and package-manager configuration; do
  not add competing tools or reformat unrelated files.
- Use `PascalCase` component/type names, `camelCase` functions/variables, and
  `use...` custom Hook names. Follow the
  [Rules of React](https://react.dev/reference/rules): keep rendering pure, call
  Hooks consistently at the top level of components/custom Hooks, and treat
  props and state as immutable.
- Type props and API boundaries. Prefer `unknown` plus narrowing over `any`;
  avoid unchecked casts and non-null assertions that conceal missing cases.
  [TypeScript types](https://www.typescriptlang.org/docs/handbook/2/everyday-types.html)
  do not validate network data at runtime.
- Centralize API calls in services and use the documented contract. Keep domain
  logic out of presentation components. Do not reinterpret backend money strings
  as authoritative floating-point calculations or trust browser totals at checkout.
- Use semantic HTML, labels, keyboard navigation, visible focus, and accessible
  status/error messages. Cover loading, empty, error, and success states. Label
  synthetic data and distinguish unverified claims from verified facts.
- Keep secrets server-side:
  [Vite exposes `VITE_` values to browser code](https://vite.dev/guide/env-and-mode.html).
  A public PayPal client ID is different from a server-only secret.
- Test meaningful interactions and API error states using the tooling established
  by the frontend owner. Include responsive and keyboard checks when UI changes.

The frontend now provides `npm.cmd run build` (TypeScript and Vite),
`npm.cmd run lint` (Oxlint), and `npm.cmd test` (native Node TypeScript tests;
Node 22.18+). Run these checks from a feature worktree's `frontend/` directory.
Follow the [local development guide](docs/local-development.md) for the central
runtime, dependencies, Ollama 0.24.0/Qwen3, Tesseract and per-machine PayPal sandbox
credentials. Keep services and retained demo data outside all Git checkouts.

## FairMade domain rules and review expectations

Accounts are general FairMade accounts and default to buyer. Seller access is
additive and requires the approved verification process; a pending application
does not grant it. Do not invent verification criteria or add role-grant shortcuts.

Respect mandatory Quality Locks. Label seller reports, estimates, source dates,
and verified evidence distinctly. Do not invent local prices, certifications,
supplier stock, or an objective fairness verdict. AI may assist extraction and
explanation; validated deterministic calculations remain authoritative.

Keep examples synthetic, contracts current, and checks proportionate to the
change. Report what passed, failed, or could not run. For documentation-only
changes, inspect links, consistency, and whitespace; application test runs are
unnecessary unless behavior or executable instructions changed materially.
