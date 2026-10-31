# Stacked PR integration incident and prevention

## What happened

GitHub merge metadata and fetched Git history show this sequence on 2026-10-31:

| UTC time | PR | Merge destination |
| --- | --- | --- |
| 04:52:00 | #9 seller pricing reviews | main |
| 04:53:00 | #10 development rules | main |
| 04:53:50 | #11 Passports | feat/seller-pricing-reviews |
| 04:54:33 | #12 contribution/security guidelines | docs/maintainable-code-rules |
| 04:55:37 | #13 marketplace listings | feat/fair-price-passports |

All five PRs were merged, but main contained only #9 and #10. The later child
merges changed retained feature branches. They did not update main.

The workflow allowed ready-to-merge stacked PRs and relied on a dependency list
without an enforced promotion step after parent merges. The agent presented them
as ready and failed to explain that the child bases needed reconciliation. This
was a workflow failure, not lost work or a user merge failure. Squash merges also
gave main different parent commit identities; blindly changing a PR base or
checking the original head's ancestry is not a safe integration audit.

The recovery PR #14 replays the three approved child commits onto current main
with attribution. Its backend/docs tree matches the merged marketplace branch;
its root rules and CONTRIBUTING.md match the merged contribution branch.
All 417 backend tests, lint, and formatting passed on the recovered tree.

## Recurrence and stricter correction

The next audit found #14 on main, but #15/#16 were merged into
fix/integrate-approved-features and #17 into feat/orders-inventory. Drafts had been
promoted and merged without first changing their destinations. Main still lacked
the guard itself, inventory/orders and PayPal checkout.

Keeping feature-targeted PRs draft was insufficient for this manual merge process.
The correction removes feature-branch destinations entirely: EVERY newly created
PR targets main, including dependent drafts. Branches may still depend on other
branches, so development can continue. Dependent main PRs clearly disclose their
cumulative changes and stay draft until their prerequisites are integrated.
The readiness guard now rejects non-main bases in Draft mode too. Recovery replays
the reviewed changes onto current main without force-pushes or agent merges.

## Required workflow

- Continue independent/dependent development without waiting for unrelated merges.
  Create every PR with main as its destination. Dependent PRs remain drafts with
  explicit prerequisites and cumulative-diff disclosures.
- Present only main-targeted PRs as merge-ready. After a parent merges, verify
  the actual merge commit on fetched main, reconcile the child's history/diff,
  retain main as the destination, revalidate, and run the Review guard before marking it ready.
- Preserve the prohibition on unauthorized force-pushes. If a published child's
  squash history cannot be reconciled without rewriting it, use a fresh main-based
  worktree/branch and replay only its changes. Leave the original draft with a
  superseding-PR reference.
- After reported merges, check destinations, merge commits, and intended feature
  files on main. Recover feature-branch-only merges through a separate main PR.

## Read-only guard

From a feature worktree, with Git and authenticated GitHub CLI available:

```powershell
# Before promoting a main-targeted draft or reporting a main PR ready:
.\scripts\Test-PullRequestReadiness.ps1 -PullRequest 14 -Mode Review
# While a main-targeted draft waits for prerequisites:
.\scripts\Test-PullRequestReadiness.ps1 -PullRequest 15 -Mode Draft
# After a user reports merging a main-targeted PR:
.\scripts\Test-PullRequestReadiness.ps1 -PullRequest 14 -Mode Integrated
# Offline guard regression checks:
.\scripts\tests\Test-PullRequestReadiness.Tests.ps1
```

Numbers above are illustrative except recovery PR #14; historical #15 itself
failed this stricter rule. Every mode requires main as the destination. Review checks GitHub base,
open state, clean matching local branch/head, and ancestry of fetched main.
Integrated checks MERGED, main destination, and merge-commit ancestry on main.
The guard fails closed on metadata/fetch failures. It does not merge, change PR
state, rewrite branches, or replace application tests and diff review.

This guard is mandatory agent/contributor workflow; it is not an installed
server-side branch-protection rule. Maintainers can still manually bypass draft
status or skip the script. Repository rulesets/required checks would be a separate
approved configuration change. The draft gate provides GitHub's merge block while
dependencies remain unresolved.

References:
[GitHub draft PR behavior](https://docs.github.com/en/pull-requests/reference/pull-requests#draft-pull-requests)
and [GitHub squash-merge ancestry](https://docs.github.com/en/pull-requests/reference/pull-request-merges#squash-and-merge-your-commits).
