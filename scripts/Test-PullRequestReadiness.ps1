# Read-only PR gate: fetches refs, but never changes branches or merges a PR.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 2147483647)]
    [int]$PullRequest,
    [ValidateSet('Review', 'Draft', 'Integrated')]
    [string]$Mode = 'Review'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$prJson = & gh api "repos/{owner}/{repo}/pulls/$PullRequest"
if ($LASTEXITCODE -ne 0) { throw 'Could not load PR metadata from GitHub.' }
$raw = ($prJson -join [Environment]::NewLine) | ConvertFrom-Json
# The REST fields also work with older installed gh versions that do not expose
# headRefOid through 'gh pr view --json'.
$pr = [pscustomobject]@{
    state = if ($raw.merged) { 'MERGED' } else { $raw.state.ToUpperInvariant() }
    isDraft = $raw.draft
    baseRefName = $raw.base.ref
    headRefName = $raw.head.ref
    headRefOid = $raw.head.sha
    mergeCommit = if ($raw.merge_commit_sha) { [pscustomobject]@{oid = $raw.merge_commit_sha} } else { $null }
}

if ($pr.baseRefName -ne 'main') {
    throw "PR #$PullRequest targets '$($pr.baseRefName)', not main. Every PR, including drafts, must target main."
}

if ($Mode -eq 'Draft') {
    if ($pr.state -ne 'OPEN' -or -not $pr.isDraft) {
        throw 'Dependent work must remain an OPEN draft PR while prerequisites are unmerged.'
    }
    Write-Output "PR #$PullRequest is draft; base is $($pr.baseRefName). It is not merge-ready."
    return
}

& git fetch origin
if ($LASTEXITCODE -ne 0) { throw 'Could not refresh origin refs.' }

if ($Mode -eq 'Integrated') {
    if ($pr.state -ne 'MERGED' -or $null -eq $pr.mergeCommit) {
        throw 'The PR has not been merged into main.'
    }
    & git merge-base --is-ancestor $pr.mergeCommit.oid origin/main
    if ($LASTEXITCODE -ne 0) { throw 'The recorded merge commit is absent from origin/main.' }
    Write-Output "PR #$PullRequest is merged and its merge commit is present on origin/main."
    return
}

if ($pr.state -ne 'OPEN') { throw 'Only an OPEN PR can be prepared for review.' }
$localBranch = & git branch --show-current
if ($LASTEXITCODE -ne 0 -or $localBranch -ne $pr.headRefName) {
    throw 'Run the review gate from the PR feature worktree.'
}
$localHead = & git rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $localHead -ne $pr.headRefOid) {
    throw 'The local commit does not match the published PR head.'
}
$dirtyFiles = & git status --porcelain
if ($LASTEXITCODE -ne 0 -or $dirtyFiles) { throw 'The feature worktree must be clean.' }
& git merge-base --is-ancestor origin/main HEAD
if ($LASTEXITCODE -ne 0) {
    throw 'The feature head does not contain current origin/main; reconcile the stack safely first.'
}
Write-Output "PR #$PullRequest passes the main-base/head/ancestry gate. Verify tests and scope before marking ready."
