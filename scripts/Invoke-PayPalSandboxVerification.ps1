# Loads only sandbox settings into this process; never evaluates configuration as code.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SettingsFile,
    [Parameter(Mandatory = $true)][string]$PythonExecutable
)

$ErrorActionPreference = 'Stop'
$taskAllowed = @(
    'FAIRMADE_PAYPAL_ENABLED',
    'FAIRMADE_PAYPAL_ENVIRONMENT',
    'FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID',
    'FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET',
    'FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID'
)
$taskFile = Get-Item -LiteralPath $SettingsFile
if ($taskFile.PSIsContainer -or $taskFile.Length -gt 16384) {
    throw 'Use a small local file containing only the five PayPal sandbox variables.'
}
if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    throw 'Pass the Python executable from the configured backend environment.'
}
$taskValues = @{}
foreach ($taskLine in [IO.File]::ReadAllLines($taskFile.FullName)) {
    $taskText = $taskLine.Trim()
    if (-not $taskText -or $taskText.StartsWith('#')) { continue }
    $taskParts = $taskText -split '=', 2
    if ($taskParts.Count -ne 2 -or $taskParts[0].Trim() -notin $taskAllowed) {
        throw 'The settings file must contain only the five documented PayPal sandbox variables.'
    }
    $taskName = $taskParts[0].Trim()
    if ($taskValues.ContainsKey($taskName)) { throw 'Duplicate sandbox setting.' }
    $taskValue = $taskParts[1].Trim()
    if ($taskValue.Length -ge 2 -and (
        ($taskValue.StartsWith('"') -and $taskValue.EndsWith('"')) -or
        ($taskValue.StartsWith("'") -and $taskValue.EndsWith("'"))
    )) { $taskValue = $taskValue.Substring(1, $taskValue.Length - 2) }
    $taskValues[$taskName] = $taskValue
}
foreach ($taskName in $taskAllowed) {
    if (-not $taskValues.ContainsKey($taskName) -or -not $taskValues[$taskName]) {
        throw "Missing sandbox setting: $taskName"
    }
}
if ($taskValues['FAIRMADE_PAYPAL_ENABLED'] -ne 'true' -or
    $taskValues['FAIRMADE_PAYPAL_ENVIRONMENT'] -ne 'sandbox' -or
    $taskValues['FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID'] -cnotmatch '^[A-Z0-9]{13}$') {
    throw 'Enable sandbox mode and supply the receiving sandbox account merchant ID.'
}

$taskOriginal = @{}
$taskNames = $taskAllowed + @('FAIRMADE_RUN_SANDBOX_PAYMENT_EVAL', 'PYTHONPATH')
foreach ($taskName in $taskNames) {
    $taskOriginal[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
}
$taskLocation = Get-Location
try {
    foreach ($taskName in $taskAllowed) {
        [Environment]::SetEnvironmentVariable($taskName, $taskValues[$taskName], 'Process')
    }
    $taskRoot = Split-Path $PSScriptRoot
    Set-Location -LiteralPath $taskRoot
    $env:PYTHONPATH = Join-Path $taskRoot 'backend/src'
    $env:FAIRMADE_RUN_SANDBOX_PAYMENT_EVAL = 'true'
    & $PythonExecutable -m pytest -q -s --tb=line -c backend/pyproject.toml `
        backend/tests/payments/test_sandbox_local.py
    $taskExit = $LASTEXITCODE
}
finally {
    foreach ($taskName in $taskNames) {
        [Environment]::SetEnvironmentVariable($taskName, $taskOriginal[$taskName], 'Process')
    }
    Set-Location -LiteralPath $taskLocation
}
exit $taskExit
