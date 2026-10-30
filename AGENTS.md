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

## Engineering and Safety Principles

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
3. Before starting new work, fetch the latest remote changes in the main worktree and create the feature worktree from `origin/main`.
4. For an existing feature worktree, rebase its branch onto the latest `origin/main` before continuing, coordinating if there are uncommitted changes or conflicts.
5. Complete and validate changes in the feature worktree. Describe changed files and verification results.
6. Standing approval covers in-scope `git add`, `git commit`, normal `git push` to the corresponding feature/issue branch, and `gh pr create` / `gh pr edit` from its dedicated worktree. Automate these actions without repeated approval. Before opening or updating a PR, run `git fetch origin` followed by `git rebase origin/main` in that feature worktree. Merging, direct pushes to `main`, out-of-scope work, and rewriting remote history are not covered by standing approval.
7. After rebasing an already-published feature branch, update the remote branch with `git push --force-with-lease` **only when explicitly authorized**. Never force-push `main`.
8. Prefer squash merges to keep `main` history clean. Never overwrite another developer's changes to resolve a conflict without reviewing them together.

## Agent Communication

- State which files will change, what the change accomplishes, and which tests or checks were run.
- If something depends on the other developer or an undefined API contract, flag that dependency rather than guessing.
- Keep explanations beginner-friendly when working with the frontend developer.
- Ask before work outside the assigned scope, merging, or rewriting remote history. In-scope shared instruction changes, staging, commits, normal feature-branch pushes, and PR creation/updates follow the standing authorization above; do not request repeated approval.

## Selecting a Specialist Agent

- Root `AGENTS.md` is the shared rulebook for both developers; it does not impose a repository-wide backend-only role.
- At the start of a chat, read `FAIRMADE_AGENT_ROLE` from the process environment. The configured dropdown agents set it to `frontend` or `backend`.
- For `frontend`, explicitly read and follow `frontend/AGENTS.md` before planning or editing. For `backend`, explicitly read and follow `backend/AGENTS.md`. Resolve paths from the active FairMade checkout root, including in feature worktrees.
- If no role is set, infer the role from the user's requested application directory and load its instructions. If the task does not establish a role, ask which role is intended before application changes. Shared-only work can proceed within its requested scope.
- A role selection is an instruction boundary, not filesystem access control. Reading API context in the other application is allowed; editing it needs explicit scope authorization.
- After creating or switching feature worktrees, reread shared and applicable specialist instructions from the destination checkout. If a required instruction file is missing, report it rather than silently working without it.
- Setup and dropdown registration: see `docs/agent-setup.md`.