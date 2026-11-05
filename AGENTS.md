# FairMade — Shared AI Agent Instructions

## Project Overview

FairMade is an AI-powered marketplace and business intelligence platform for independent sellers and buyers. Its goal is to help sellers earn sustainable profits **without compromising product quality**, while giving buyers transparent, evidence-based information about price and value.

Primary experiences:
- **Seller:** manage products; calculate true production costs, labor, and overhead; compare local suppliers and quality; establish non-negotiable Quality Lock requirements; review AI-assisted pricing and savings recommendations; manage sales.
- **Buyer:** browse products; compare relevant local alternatives; see a seller-approved Fair Price Passport with costs, quality information, and evidence; ask for explanations; complete a PayPal purchase.

The app should not equate "fair" with either the highest achievable seller price or the lowest buyer price. Do not claim that a price is objectively fair without sufficient evidence. Label seller-reported inputs, model estimates, and verified sources clearly.

## Repository Structure and Ownership

```text
FairMade/
├── AGENTS.md                 # Shared instructions (this file)
├── frontend/
│   └── AGENTS.md             # React/TypeScript frontend instructions
├── backend/
│   └── AGENTS.md             # Python/FastAPI backend instructions
├── docs/
│   └── api-contract.md      # Shared API contract (when created/approved)
└── scripts/                 # Development utilities
```

- The **frontend developer** owns UI and browser-side integration in `frontend/`.
- The **backend developer** owns APIs, business logic, data, AI orchestration, and payment handling in `backend/`.
- Both developers jointly review shared documentation, API contracts, and changes to repository-wide configuration.
- Follow the more specific `AGENTS.md` within the directory you are editing.
- Do not modify the other developer's application directory without explicit permission.

## Collaboration and API Contract

- Maintain clear separation between the frontend and backend. Communicate through documented HTTP APIs and JSON payloads.
- Agree on endpoint paths, methods, required/optional fields, units, money representation, authentication, response shapes, and error formats **before relying on them**.
- Keep the shared agreement in `docs/api-contract.md`. Treat proposed endpoints as proposals until both developers accept them; do not claim unimplemented endpoints exist.
- Prefer nonbreaking API changes. For a proposed breaking change, explain the impact on both applications and obtain agreement before implementing it.
- Use mock frontend data for features whose backend endpoints are not ready; clearly identify mock/demo data.
- Coordinate integration testing, especially for seller pricing analysis, buyer explanations, and PayPal checkout.

## Design, Maintainability, and Readability

These development rules apply to both frontend and backend work.

- Build small, cohesive modules with clear responsibilities and explicit interfaces. Keep presentation, HTTP transport, business rules, persistence, and external integrations separate where applicable.
- Keep features loosely coupled. Share reusable behavior through focused services, domain functions, or helpers rather than depending on another feature's route handlers or implementation details. Avoid circular dependencies and duplicated business rules.
- Design for reasonable growth in data and usage through bounded inputs, pagination, and efficient data access where relevant. Do not introduce speculative abstractions, infrastructure, or major architectural changes without a demonstrated need and the required approval.
- Prefer human-readable code: descriptive names, small focused functions, and straightforward control flow. Break complex decisions into named steps; avoid dense nested conditionals, clever one-liners, and functions that mix unrelated responsibilities.
- Use comments and documentation to explain intent, invariants, and tradeoffs rather than restating the code. Keep public interfaces and important assumptions documented.
- Apply these principles incrementally within the current task. Refactor existing code when needed to keep the change maintainable; do not turn a focused feature into an unrelated repository-wide rewrite.

## Engineering and Safety Principles

- Consider application security throughout design, implementation, and review for both backend and frontend. Apply least privilege, backend authorization and ownership checks, bounded input validation, safe output handling, and privacy-preserving response schemas. Protect secrets and session tokens; use secure framework patterns and test relevant abuse/failure cases. Keep controls proportionate to the feature and distinguish local MVP limitations from hosted readiness.
- Follow the coding standards and contribution workflow in [CONTRIBUTING.md](CONTRIBUTING.md), together with the applicable specialist instructions and checked-in tool configuration. Use established Python and React/TypeScript conventions, useful types, and existing formatters/linters; update the guide as agreed practices evolve rather than introducing competing conventions.
- Record local MVP tradeoffs in [docs/local-mvp-decisions.md](docs/local-mvp-decisions.md). Update the relevant entry when choosing, implementing, or retiring temporary behavior; include decision evidence, current status, limitations, and the follow-up needed beyond local development. Distinguish confirmed user choices from implementation limits and unresolved decisions. A follow-up entry does not authorize new scope or infrastructure.

- Prefer incremental, modular, maintainable, testable changes over large rewrites.
- Inspect relevant existing instructions and code before making changes. Explain intended scope and material decisions before large modifications.
- Do not introduce paid APIs or services, major architectural changes, or new infrastructure without approval.
- Never commit credentials, API keys, access tokens, secrets, or real payment information. Keep server-only secrets out of frontend bundles and Git history.
- Do not generate unsupported local prices, quality certifications, supplier availability, or seller cost claims. Where evidence is incomplete, show sources, dates, limitations, and uncertainty.
- AI recommendations must respect mandatory quality, safety, and ethical requirements. An option that fails a Quality Lock must not be presented as an acceptable cost saving.
- Use deterministic, tested calculations for money, margins, and unit conversions. AI can extract, compare, and explain; it must not silently invent costs or override validated calculations.
- PayPal payments must use supported APIs and the **sandbox** for development. Treat payment completion as confirmed only after backend verification, not a frontend button click.
- Follow the user's requested scope; do not build unrelated features automatically.

## Git Worktree and Pull Request Workflow

1. Reserve the primary worktree for maintaining local `main`. Update it with `git pull --ff-only`; do not develop, test, commit, or rebase there.
2. Create a **separate branch and worktree outside the main worktree for each issue or feature**, including documentation and repository-instruction changes.
3. Before starting new work, fetch the latest remote changes in the main worktree. Start independent features from `origin/main`. Do not wait for unrelated PRs to merge. Dependent work may use its own branch/worktree from an unmerged parent, but EVERY PR, including drafts, MUST target `main` (`--base main`). Never use another feature branch as a PR destination. Keep dependent PRs draft and explicitly list prerequisite PRs and any prerequisite changes included in the cumulative diff.
4. Before continuing an existing feature, fetch and synchronize its worktree with current `origin/main`, or its current development parent while that prerequisite remains unmerged. Rebase unpublished work. For a published feature branch, prefer merging the updated development base into the feature branch and pushing normally; this preserves published history and does not authorize a PR merge into main. Review conflicts against both sides and coordinate independent edits rather than overwriting them. Rebasing published history still requires explicit remote-rewrite authorization before pushing.
5. Complete and validate changes in the feature worktree. Describe changed files and verification results.
6. Standing approval covers in-scope `git add`, `git commit`, normal `git push` to the corresponding feature/issue branch, and `gh pr create` / `gh pr edit` from its dedicated worktree. Automate these actions without repeated approval. Before opening or updating a PR, fetch and synchronize using rule 4; the PR destination remains `main` regardless of the development parent. Document dependencies and validate the combined tree. After parent merges, follow rule 10 before presenting the child for review. PR merges into main, direct pushes to `main`, out-of-scope work, and rewriting remote history are not covered by standing approval.
7. After rebasing an already-published feature branch, update the remote branch with `git push --force-with-lease` **only when explicitly authorized**. Never force-push `main`.
8. Prefer squash merges to keep `main` history clean. Never overwrite another developer's changes to resolve a conflict without reviewing them together.
9. Only PRs targeting `main` may be marked ready or presented to the user as ready to merge. Before that transition, run `scripts/Test-PullRequestReadiness.ps1 -PullRequest <number> -Mode Review` from the clean, validated feature worktree; it must pass. Verify the actual GitHub base, published head, current-main ancestry, and final diff. For a dependent draft, use `-Mode Draft` while its parent is unmerged.
10. After every parent merge, the agent must fetch and verify its merge commit on `origin/main`, then refresh each dependent child before presenting it as ready. A squash merge creates different commit identities; merging PRs in order does not refresh child branches. For a published child, normally merge `origin/main` into its feature branch, resolve conflicts by reviewing the parent and child changes, and push normally. For an unpublished child, replay only the child commits onto current main (for example, `git rebase --onto origin/main <old-parent-tip>`). Revalidate, inspect the main-targeted diff to ensure it contains only the remaining work, and pass the Review guard. Do not tell the user to merge a dependency stack consecutively without this agent refresh between parent and child merges. If safe synchronization requires an unauthorized history rewrite, create a replacement branch/worktree from current main, replay only the child changes, and open a main-targeted replacement PR; keep the old PR draft and identify its replacement. Never merge a child into a retired parent branch.
11. A GitHub MERGED label alone does not establish main integration. After the user reports merges, audit each PR's base and merge commit using `-Mode Integrated`; verify intended files/features on fetched main before reporting them integrated or basing independent work on them. If changes landed only on a feature branch, prepare a main-targeted recovery PR without merging it yourself. See [the incident and recovery procedure](docs/stacked-pr-integration.md).

## Optional Continuous Feature Workflow

- This workflow is **optional and disabled by default**. Activate it only when the user explicitly requests the continuous feature cycle. A request for one feature, an explanation of the workflow, or permission to document it does not activate the cycle.
- When explicitly activated, review the user's supplied feature list, implemented code, open PRs, dependencies, priority, and current need. Select the highest-priority remaining feature within the assigned role; do not duplicate work already implemented or under review.
- Implement each selected feature in its own branch/worktree, validate it, commit and push it, and open its PR. Once those steps are complete, move directly to the next priority feature without waiting for a merge or another instruction to continue.
- Use current main for independent features. Dependent development may continue from an unmerged parent, but its PR still targets main and remains draft until the parent is integrated and the child is refreshed and validated under the Git workflow above.
- Ask for the user's decision when a material product/design choice cannot be resolved from existing instructions. Present the question visibly as specified below and pause work that depends on the answer; continue independent authorized work where useful. Routine implementation choices and already-authorized actions do not require repeated confirmation.
- Stop the cycle when the user asks to pause/stop, its explicitly authorized scope or duration ends, or all features from the supplied list are implemented or already covered by open PRs. Report the remaining/review status and ask the user what to do next rather than inventing new scope. After a pause or stop, resume the cycle only when explicitly requested.
- Enabling the cycle does not authorize PR merges, remote history rewrites, paid services, major infrastructure changes, or edits outside the assigned ownership boundary. Documenting this workflow does not enable it.

## Agent Communication

- State which files will change, what the change accomplishes, and which tests or checks were run.
- If something depends on the other developer or an undefined API contract, flag that dependency rather than guessing.
- Keep explanations beginner-friendly when working with the frontend developer.
- Ask before work outside the assigned scope, merging, or rewriting remote history. In-scope shared instruction changes, staging, commits, normal feature-branch pushes, and PR creation/updates follow the standing authorization above; do not request repeated approval.
- Make decision questions visible in ordinary chat, with concise numbered choices and the recommended option identified when useful. Structured choice prompts may supplement the chat question; never rely on a popup as the only place the question or options appear.
- A prompt tool returning `accepted` acknowledges submission, not display or a user answer. Do not claim the user saw a prompt, or treat silence, timeout, a preselected choice, or a missing popup as consent or refusal.
- When an actual decision or approval is required, end the response with the complete question and choices in chat, and wait for the user's reply before dependent work. If the user reports a missing prompt, restate it directly in chat. Distinguish confirmed delivery evidence from assumptions about IDE behavior.

## Selecting a Specialist Agent

- Root `AGENTS.md` is the shared rulebook for both developers; it does not impose a repository-wide backend-only role.
- At the start of a chat, read `FAIRMADE_AGENT_ROLE` from the process environment. The configured dropdown agents set it to `frontend` or `backend`.
- For `frontend`, explicitly read and follow `frontend/AGENTS.md` before planning or editing. For `backend`, explicitly read and follow `backend/AGENTS.md`. Resolve paths from the active FairMade checkout root, including in feature worktrees.
- If no role is set, infer the role from the user's requested application directory and load its instructions. If the task does not establish a role, ask which role is intended before application changes. Shared-only work can proceed within its requested scope.
- A role selection is an instruction boundary, not filesystem access control. Reading API context in the other application is allowed; editing it needs explicit scope authorization.
- After creating or switching feature worktrees, reread shared and applicable specialist instructions from the destination checkout. If a required instruction file is missing, report it rather than silently working without it.
- Setup and dropdown registration: see `docs/agent-setup.md`.
