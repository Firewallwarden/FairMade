# FairMade submission packet

Prepared for the [PayPal AI Hackathon](https://paypalaihackathon.devpost.com/).
This file is submission copy and a release checklist, not evidence that the
repository, video or Devpost entry has already been published.

## Project name and tagline

**FairMade**

Understand the price. Protect the quality. Complete the purchase with PayPal.

## Description for the submission form

FairMade helps independent makers understand what their products cost to produce
and helps buyers understand what they are paying for. Our prototype connects
seller economics, evidence-based AI explanations and PayPal sandbox checkout in
one marketplace experience.

A seller can record ingredients, labor, packaging and overhead for products such
as sourdough bread and eggs. The Fair Price Engine calculates costs, break-even
prices and margin scenarios deterministically. Quality Locks exclude alternatives
that fail mandatory requirements, even when they are cheaper. Supplier records
retain dates and evidence labels rather than inventing local market prices.

Local Qwen3 AI explains selected business evidence, helps draft product copy and
supports follow-up questions. Receipt OCR and AI extraction produce drafts that
require seller review before becoming expenses. AI does not set authoritative
monetary totals, approve substitutions or publish private information.

Sellers choose what to disclose in a Fair Price Passport. Buyers browse approved
listings, inspect those disclosures and ask the buyer assistant for explanations.
Missing information stays unknown; FairMade does not certify that any price is
objectively fair.

PayPal is the transaction layer connecting that decision to an actual sandbox
purchase. The browser uses PayPal's checkout SDK; the backend creates the order
from authoritative listing data and verifies capture before recording payment and
updating inventory. Order history, pickup, participant messages and seller-reviewed
refund workflows continue the experience after checkout. This is a local prototype
using a shared sandbox merchant, not a production multi-seller payout service.

Judges can run the React desktop-browser frontend and FastAPI backend using the
repository's setup instructions. AI requires the documented local model setup;
checkout requires privately configured PayPal sandbox credentials. Neither feature
is replaced with a simulated success when its provider is unavailable.

## Tools and how they are used

| Tool | Role in FairMade |
| --- | --- |
| PayPal JavaScript SDK, sandbox Orders and Payments REST APIs | Buyer approval, backend order creation/capture, payment verification, refund and reconciliation workflows. Server-only merchant credentials never enter the frontend. |
| Qwen3 8B (`qwen3:8b`) through local Ollama | Seller/buyer evidence explanations, saved conversations, seller-reviewed description drafts and structured receipt extraction. Runtime calls go through the backend, with no automatic cloud fallback. |
| Tesseract OCR with English data | Extracts text from receipt images before model-assisted draft extraction; this is OCR, not a language model. |
| React, TypeScript, Vite and Tailwind CSS | Browser interface and frontend build. |
| Python, FastAPI and Pydantic | HTTP APIs, validation, authorization, deterministic calculations and AI/payment orchestration. |
| SQLite, SQLAlchemy and Alembic | Local persistence and explicit schema migrations. |
| pytest, Ruff, native Node tests, Oxlint and Playwright | Automated validation; provider-disabled tests and real-provider acceptance are reported separately. |
| OpenAI Codex in JetBrains IDEs | Development assistance for implementation, review, tests and documentation; distinct from the Qwen model used inside the product. No exact development-model version is asserted here. |

Sponsor tools are optional. Do not select a sponsor-specific prize or claim use
of a sponsor product unless its actual integration can be demonstrated.

## Hackathon-period progress

The submitter must confirm the team's actual work dates and describe significant
updates if this project predates the event. Use the repository history as supporting
evidence; do not treat commit timestamps alone as proof of eligibility. Suggested
evidence includes pricing/Quality Locks, local AI workflows, sandbox commerce,
seller disclosure controls and integrated browser workflows. Include only work
actually completed during the submission period.

## Links for the form

- Source: https://github.com/Firewallwarden/FairMade
- Run instructions: [judge quick start](judge-quickstart.md).
- Intended device/platform: Windows desktop/laptop, supported browser; local API,
  SQLite, local Ollama model and optional receipt OCR installation.
- Public YouTube video: **pending recording/upload to the user's mfranca915 channel**.
- Hosted demo: not supplied; use the documented runnable local build route.

## Final release gates

| Requirement | Evidence or remaining action |
| --- | --- |
| Meaningful PayPal integration | Show real sandbox approval followed by backend-verified paid order. See [payment evidence](paypal-verification.md). |
| Meaningful runtime AI | Show an actual Qwen answer using the selected product's evidence, not only development-tool use. |
| Working prototype | [Setup](judge-quickstart.md) and [frontend acceptance](../frontend/e2e/ACCEPTANCE.md). The separate verification workflow passed 12 real AI/OCR checks and 6 real sandbox checkout/refund checks, including setup checks, on desktop and narrow Chromium. Evidence integrated in main via PR #98. |
| Text and tool disclosure | Copy the description and tools above; reconcile against the final demonstrated build. |
| Public open-source repository | Owner changed visibility to Public; GitHub metadata confirms `isPrivate: false`. Secret scan completed as described below. Recheck anonymous access before submitting. |
| Detectable root license | Owner selected MIT. Standard root [LICENSE](../LICENSE) is included in PR #99; merge it and verify GitHub detects MIT on main. Third-party asset licenses remain in effect. |
| Public video under 3 minutes | Record actual functioning desktop app, upload to mfranca915 as Public and paste the watch URL into Devpost. [Recording plan](demo-video.md). |
| Rights to materials | Retain [photo credits](../frontend/README.md#asset-credits) and font OFL files. Review the final recording for third-party material; omit unapproved logos/music. |
| Submitter information and eligibility | Submitter completes eligibility, ownership, team and rule attestations in Devpost. |
| Final submission | Check all links signed out, save and submit the form, then retain its submission confirmation. A draft is not a submitted entry. |

The deadline is November 12, 2026 at noon Pacific (2 p.m. America/Chicago).
The [official rules](https://paypalaihackathon.devpost.com/rules) also require
English materials and free judge access through December 15, 2026, 8 a.m. Pacific.
Use private access instructions if any special access is needed; never publish
server secrets in the repository, video or public form text.

## Publication checks performed by this chat

On November 12, Gitleaks 8.30.1 scanned all fetched Git refs (188 commits,
approximately 6.16 MB) with redacted output and reported no leaks. The official
release archive's SHA-256 was checked against its release checksum file. No
tracked or historical database, private-key, environment, settings.json or
credential files matched the checked filename patterns. These checks do not
prove absence of every possible secret or private detail. Scanner files and
redacted output remain outside Git under the local submission-audit directory.
The visibility update failed; read-only metadata confirmed Write access without
Admin permission. No repository setting change is claimed.
The owner subsequently changed visibility to Public; API metadata now confirms
the repository is public. The owner also selected MIT, included in this PR's root
LICENSE. Detection on the default branch remains a post-merge check.

## Evidence handoff from the integration chat

Before closing the release gates, record: tested commit; clean runtime source
revision; backend/frontend check outcomes; real AI outcome; real sandbox capture
outcome; receipt outcome if shown; remaining skips or failures. Existing linked
results are historical and must not be relabeled as this chat's test run.

Update: PR #98 integrated the separate workflow's real-provider acceptance on
main `73817fb`. Its application baseline was `d1039f4`; the PR changes test
tooling/evidence, not application behavior. AI/OCR run
`5e052632-beac-4776-a48a-89075851ef67` passed 12 checks and sandbox run
`17c78e5b-a8d6-46f0-9e18-3be1e6933717` passed 6, with no failures/skips in
those final runs. The full [acceptance record](../frontend/e2e/ACCEPTANCE.md#subsequent-real-provider-acceptance)
preserves earlier failed attempts and coverage limits. No new test run is
attributed to the submission-documentation chat.
