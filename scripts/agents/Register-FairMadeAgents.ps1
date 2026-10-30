<#
.SYNOPSIS
Registers FairMade specialist agents with JetBrains AI Chat using installed Codex ACP.
.DESCRIPTION
Merges only the two FairMade entries. Preserves unrelated agents and settings,
backs up an existing configuration, and refuses display-name collisions.
Does not install packages, change authentication, or relax sandbox permissions.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$NodePath,
    [Parameter(Mandatory = $true)]
    [string]$AdapterPath,
    [string]$ConfigPath = (Join-Path $env:USERPROFILE '.jetbrains/acp.json')
)

$ErrorActionPreference = 'Stop'
$nodeExecutable = (Resolve-Path -LiteralPath $NodePath).ProviderPath
$adapterEntry = (Resolve-Path -LiteralPath $AdapterPath).ProviderPath
if (-not (Test-Path -LiteralPath $nodeExecutable -PathType Leaf) -or
    -not (Test-Path -LiteralPath $adapterEntry -PathType Leaf)) {
    throw 'NodePath and AdapterPath must point to installed files.'
}

$templatePath = Join-Path $PSScriptRoot 'acp.template.json'
$template = Get-Content -Raw -Encoding UTF8 -LiteralPath $templatePath | ConvertFrom-Json
$configFile = [System.IO.Path]::GetFullPath($ConfigPath)
$configExists = Test-Path -LiteralPath $configFile
$config = if ($configExists) {
    Get-Content -Raw -Encoding UTF8 -LiteralPath $configFile | ConvertFrom-Json
} else {
    [pscustomobject]@{}
}
if ($config -isnot [pscustomobject]) {
    throw 'Existing ACP configuration must be a JSON object.'
}
if (-not $config.PSObject.Properties['agent_servers']) {
    $config | Add-Member -NotePropertyName 'agent_servers' -NotePropertyValue ([pscustomobject]@{})
}
if ($config.agent_servers -isnot [pscustomobject]) {
    throw 'agent_servers must be a JSON object; existing configuration was not changed.'
}

foreach ($agentProperty in $template.agent_servers.PSObject.Properties) {
    $displayName = $agentProperty.Name
    $agentEntry = $agentProperty.Value
    $existing = $config.agent_servers.PSObject.Properties[$displayName]
    if ($existing -and
        $existing.Value.env.FAIRMADE_AGENT_ROLE -ne $agentEntry.env.FAIRMADE_AGENT_ROLE) {
        throw "Agent name '$displayName' is already used by another configuration; no changes written."
    }
    $agentEntry.command = $nodeExecutable
    $agentEntry.args = @($adapterEntry)
    $config.agent_servers | Add-Member -NotePropertyName $displayName -NotePropertyValue $agentEntry -Force
}

$json = $config | ConvertTo-Json -Depth 100
$configDirectory = Split-Path -Parent $configFile
[System.IO.Directory]::CreateDirectory($configDirectory) | Out-Null
if ($configExists) {
    $backupFile = "$configFile.$([guid]::NewGuid().ToString('N')).bak"
}
# Same-directory temporary file avoids truncating an existing configuration on a write failure.
$temporaryFile = "$configFile.$([guid]::NewGuid().ToString('N')).tmp"
[System.IO.File]::WriteAllText($temporaryFile, $json, (New-Object System.Text.UTF8Encoding($false)))
if ($configExists) {
    [System.IO.File]::Replace($temporaryFile, $configFile, $backupFile)
} else {
    [System.IO.File]::Move($temporaryFile, $configFile)
}
Write-Output "Registered Frontend Agent and Backend Agent in $configFile"
