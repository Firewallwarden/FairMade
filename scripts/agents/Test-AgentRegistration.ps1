<# Offline registration checks; no agents, models, or payment services are invoked. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$NodePath,
    [Parameter(Mandatory = $true)][string]$AdapterPath
)
$ErrorActionPreference = 'Stop'
$testDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('fairmade-agent-test-' + [guid]::NewGuid())
[System.IO.Directory]::CreateDirectory($testDirectory) | Out-Null
$testConfig = Join-Path $testDirectory 'acp.json'
$registerScript = Join-Path $PSScriptRoot 'Register-FairMadeAgents.ps1'

function Assert-Condition([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

& $registerScript -NodePath $NodePath -AdapterPath $AdapterPath -ConfigPath $testConfig | Out-Null
$registered = Get-Content -Raw -LiteralPath $testConfig | ConvertFrom-Json
Assert-Condition ($registered.agent_servers.'Frontend Agent'.env.FAIRMADE_AGENT_ROLE -eq 'frontend') 'Frontend role missing'
Assert-Condition ($registered.agent_servers.'Backend Agent'.env.FAIRMADE_AGENT_ROLE -eq 'backend') 'Backend role missing'
foreach ($agent in $registered.agent_servers.PSObject.Properties) {
    Assert-Condition ($agent.Value.command -eq (Resolve-Path -LiteralPath $NodePath).ProviderPath) 'Incorrect executable'
    Assert-Condition ($agent.Value.args[0] -eq (Resolve-Path -LiteralPath $AdapterPath).ProviderPath) 'Incorrect adapter'
    $codexSettings = $agent.Value.env.CODEX_CONFIG | ConvertFrom-Json
    Assert-Condition ($codexSettings.developer_instructions -match ($agent.Value.env.FAIRMADE_AGENT_ROLE + '/AGENTS.md')) 'Role instructions missing'
    Assert-Condition (-not $codexSettings.PSObject.Properties['approval_policy']) 'Approval policy changed'
    Assert-Condition (-not $codexSettings.PSObject.Properties['sandbox_mode']) 'Sandbox policy changed'
}

$original = '{"default_mcp_settings":{"use_idea_mcp":false},"extra_setting":"preserve","agent_servers":{"Existing Agent":{"command":"leave-alone","env":{"example":"keep"}}}}'
[System.IO.File]::WriteAllText($testConfig, $original)
& $registerScript -NodePath $NodePath -AdapterPath $AdapterPath -ConfigPath $testConfig | Out-Null
$merged = Get-Content -Raw -LiteralPath $testConfig | ConvertFrom-Json
Assert-Condition ($merged.extra_setting -eq 'preserve') 'Unrelated top-level setting lost'
Assert-Condition ($merged.default_mcp_settings.use_idea_mcp -eq $false) 'MCP defaults changed'
Assert-Condition ($merged.agent_servers.'Existing Agent'.env.example -eq 'keep') 'Unrelated agent changed'
$backups = @(Get-ChildItem -LiteralPath $testDirectory -Filter '*.bak')
Assert-Condition ($backups.Count -eq 1) 'Missing original backup'
Assert-Condition ((Get-Content -Raw -LiteralPath $backups[0].FullName) -eq $original) 'Backup changed'
& $registerScript -NodePath $NodePath -AdapterPath $AdapterPath -ConfigPath $testConfig | Out-Null
$rerun = Get-Content -Raw -LiteralPath $testConfig | ConvertFrom-Json
Assert-Condition (@($rerun.agent_servers.PSObject.Properties).Count -eq 3) 'Repeat registration duplicated agents'

$collision = '{"agent_servers":{"Frontend Agent":{"command":"someone-else"}}}'
[System.IO.File]::WriteAllText($testConfig, $collision)
$rejected = $false
try { & $registerScript -NodePath $NodePath -AdapterPath $AdapterPath -ConfigPath $testConfig | Out-Null }
catch { $rejected = $true }
Assert-Condition $rejected 'Unrelated display-name collision was overwritten'
Assert-Condition ((Get-Content -Raw -LiteralPath $testConfig) -eq $collision) 'Collision changed existing file'

[System.IO.File]::WriteAllText($testConfig, '{invalid json')
$rejected = $false
try { & $registerScript -NodePath $NodePath -AdapterPath $AdapterPath -ConfigPath $testConfig | Out-Null }
catch { $rejected = $true }
Assert-Condition $rejected 'Malformed existing configuration was accepted'
Assert-Condition ((Get-Content -Raw -LiteralPath $testConfig) -eq '{invalid json') 'Malformed configuration was overwritten'

Write-Output 'Passed: role configuration, executable paths, JSON settings, preservation, backup, repeat registration, collision rejection, malformed JSON rejection.'
Write-Output "Test artifacts: $testDirectory"
