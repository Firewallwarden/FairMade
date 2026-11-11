# Backend conversational-continuity audit

Scope: assistant foundation plus sales/history questions, supplier explanations
and private reviewed description drafts. Browser work belongs to the frontend
developer. Larger deferred AI features remain outside this work.
Feature PRs: [#39](https://github.com/Firewallwarden/FairMade/pull/39),
[#40](https://github.com/Firewallwarden/FairMade/pull/40) and
[#41](https://github.com/Firewallwarden/FairMade/pull/41). Combined regression:
1,221 tests passed, with the separate two-request continuity audit also passing.

## Finding: conversational continuity is not yet implemented

Current seller and buyer question schemas contain no conversation identifier or
prior-turn history. Every assistant call rebuilds evidence from the supplied
scope and sends only that question, its current evidence and fixed system/example
messages to the model. No previous user questions or assistant answers are loaded
or saved as a conversation.

Sales/history support retrieves business evidence. Description drafts preserve
private copy and review provenance. Neither supplies earlier dialogue turns.
Ollama keep_alive keeps model weights loaded; it does not add dialogue history.

Consequently a follow-up such as “Why does that price lose money?” cannot reliably
identify an earlier proposed price unless the caller repeats the price/context.
The caller must continue providing explicit product/listing scope per request.
Backend tests and the API schemas must not be described as confirming retained
conversation memory.
The two-request boundary test confirms that a previous proposed price is not
replayed into a subsequent independent question or supplied as its scenario.

## Decision needed before implementation

The user was asked to choose:

1. Temporary bounded conversations in backend memory, expiring after inactivity
   and disappearing on restart (recommended for the local demo).
2. Saved database conversations with ownership, deletion and a defined retention
   policy.

No answer has been received at this audit. A submitted prompt is not consent.
No retention behavior has been silently selected.

Whichever option is chosen, implementation must bind each conversation to its
authenticated owner and seller/buyer role, bound turns and total context, and
revalidate current source access/disclosures. Withdrawn public content or earlier
private seller turns must not leak into another account or buyer conversation.
Historical chat text cannot become authoritative financial evidence or relax
Quality Locks. Deletion/expiry, retries and concurrent turns need defined behavior.

Backend continuity should then be verified with real two-turn questions, scope
changes, expiry/restart behavior, access revocation and cross-account/role tests.
Frontend can implement the browser flow against that resulting contract.

The three feature PRs do not authorize implementing receipt scanning, forecasting,
personalization or basket optimization before this continuity decision and later
scope reassessment.
