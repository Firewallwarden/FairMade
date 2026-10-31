# Offline smoke tests. Fake Git/GitHub functions make no repository or network changes.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$guardPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'Test-PullRequestReadiness.ps1'
$global:FairMadePrGuardScenario = @{}
$script:passed = 0

function gh {
    $global:LASTEXITCODE = $global:FairMadePrGuardScenario.GhExit
    if ($global:LASTEXITCODE -eq 0) {
        $metadata = $global:FairMadePrGuardScenario.Pr
        @{
            state = if ($metadata.state -eq 'MERGED') { 'closed' } else { $metadata.state.ToLowerInvariant() }
            merged = $metadata.state -eq 'MERGED'
            draft = $metadata.isDraft
            base = @{ref = $metadata.baseRefName}
            head = @{ref = $metadata.headRefName; sha = $metadata.headRefOid}
            merge_commit_sha = if ($metadata.mergeCommit) { $metadata.mergeCommit.oid } else { $null }
        } | ConvertTo-Json -Depth 5
    }
}

function git {
    $global:LASTEXITCODE = 0
    $command = $args -join ' '
    switch ($command) {
        'fetch origin' { $global:LASTEXITCODE = $global:FairMadePrGuardScenario.FetchExit }
        'branch --show-current' { $global:FairMadePrGuardScenario.Branch }
        'rev-parse HEAD' { $global:FairMadePrGuardScenario.Head }
        'status --porcelain' { $global:FairMadePrGuardScenario.Dirty }
        'merge-base --is-ancestor origin/main HEAD' { $global:LASTEXITCODE = $global:FairMadePrGuardScenario.AncestorExit }
        'merge-base --is-ancestor merged-sha origin/main' { $global:LASTEXITCODE = $global:FairMadePrGuardScenario.MergeExit }
        default { throw "Unexpected Git command in test: $command" }
    }
}

function Test-Scenario {
    param([string]$Name, [string]$Mode, [hashtable]$Changes, [bool]$ShouldPass)
    $global:FairMadePrGuardScenario = @{
        Pr = @{
            state = 'OPEN'; isDraft = $false; baseRefName = 'main'
            headRefName = 'feature'; headRefOid = 'published-sha'; mergeCommit = @{oid = 'merged-sha'}
        }
        Branch = 'feature'; Head = 'published-sha'; Dirty = ''
        GhExit = 0; FetchExit = 0; AncestorExit = 0; MergeExit = 0
    }
    foreach ($key in $Changes.Keys) {
        if ($global:FairMadePrGuardScenario.Pr.ContainsKey($key)) { $global:FairMadePrGuardScenario.Pr[$key] = $Changes[$key] }
        else { $global:FairMadePrGuardScenario[$key] = $Changes[$key] }
    }
    $succeeded = $false
    try {
        & $guardPath -PullRequest 42 -Mode $Mode | Out-Null
        $succeeded = $true
    } catch {
        if ($ShouldPass) { throw "Scenario '$Name' unexpectedly failed: $_" }
    }
    if ($succeeded -ne $ShouldPass) { throw "Scenario '$Name' unexpectedly passed." }
    $script:passed++
}

Test-Scenario 'main-ready' Review @{} $true
Test-Scenario 'main-draft-preflight' Review @{isDraft = $true} $true
Test-Scenario 'stacked-ready-rejected' Review @{baseRefName = 'feature-parent'} $false
Test-Scenario 'wrong-worktree' Review @{Branch = 'unrelated'} $false
Test-Scenario 'unpublished-head' Review @{Head = 'local-only'} $false
Test-Scenario 'dirty-worktree' Review @{Dirty = ' M example.txt'} $false
Test-Scenario 'stale-main' Review @{AncestorExit = 1} $false
Test-Scenario 'github-unavailable' Review @{GhExit = 1} $false
Test-Scenario 'fetch-unavailable' Review @{FetchExit = 1} $false
Test-Scenario 'closed-review' Review @{state = 'CLOSED'} $false
Test-Scenario 'dependent-draft' Draft @{isDraft = $true; baseRefName = 'feature-parent'} $true
Test-Scenario 'dependent-ready-rejected' Draft @{baseRefName = 'feature-parent'} $false
Test-Scenario 'merged-main' Integrated @{state = 'MERGED'} $true
Test-Scenario 'merged-feature-is-not-integration' Integrated @{state = 'MERGED'; baseRefName = 'feature-parent'} $false
Test-Scenario 'merge-absent-from-main' Integrated @{state = 'MERGED'; MergeExit = 1} $false
Test-Scenario 'still-open-is-not-integrated' Integrated @{} $false
Test-Scenario 'missing-merge-sha' Integrated @{state = 'MERGED'; mergeCommit = $null} $false
Write-Output "$($script:passed) PR readiness scenarios passed."
