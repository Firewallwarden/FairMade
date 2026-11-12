[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Start', 'Stop', 'Status')]
    [string]$Action,
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'FairMade/runtime')
)

$ErrorActionPreference = 'Stop'
$RuntimeRoot = [IO.Path]::GetFullPath($RuntimeRoot)
$statePath = Join-Path $RuntimeRoot 'processes.json'
$state = if (Test-Path -LiteralPath $statePath) { Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json } else { $null }

function Get-OwnedProcess($service) {
    if (-not $service) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($service.pid)"
    if (-not $process) { return $null }
    if (-not $process.ExecutablePath.Equals($service.executable, [StringComparison]::OrdinalIgnoreCase) -or
        $process.CreationDate.ToUniversalTime().ToString('o') -ne $service.created) {
        throw 'The saved PID belongs to another process. No process was stopped.'
    }
    return $process
}

function Stop-RuntimeProcess([int]$ProcessId) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId")
    foreach ($child in $children) {
        if ($child.CommandLine -and $child.CommandLine.Contains($RuntimeRoot)) {
            Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
        }
    }
    Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

if ($Action -eq 'Status') {
    foreach ($name in @('backend', 'frontend')) {
        $process = if ($state) { Get-OwnedProcess $state.$name } else { $null }
        Write-Output "$name`: $(if ($process) { 'running (PID ' + $process.ProcessId + ')' } else { 'stopped' })"
    }
    return
}
if ($Action -eq 'Stop') {
    if ($state) {
        foreach ($name in @('frontend', 'backend')) {
            $process = Get-OwnedProcess $state.$name
            if (-not $process) { continue }
            # Windows virtual-environment launchers may have a child Python process.
            Stop-RuntimeProcess $process.ProcessId
        }
        Remove-Item -LiteralPath $statePath
    }
    Write-Output 'Managed local runtime stopped. Database and settings retained.'
    return
}
if ($state) {
    foreach ($name in @('backend', 'frontend')) {
        if (Get-OwnedProcess $state.$name) { throw 'A managed service is already running. Use Status or Stop first.' }
    }
}
foreach ($port in @(8000, 5173)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is occupied. This script will not kill an unknown process."
    }
}
$current = Get-Content -LiteralPath (Join-Path $RuntimeRoot 'current.json') -Raw | ConvertFrom-Json
$release = [IO.Path]::GetFullPath($current.release)
if (-not $release.StartsWith($RuntimeRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or
    (Test-Path -LiteralPath (Join-Path $release '.git'))) { throw 'Invalid central release directory.' }
$settings = Get-Content -LiteralPath (Join-Path $RuntimeRoot 'private/settings.json') -Raw | ConvertFrom-Json
$previous = @{}
$backend = $null
$frontend = $null
$oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
try {
    try {
        $env:PYTHONPATH = Join-Path $release 'backend/src'
        foreach ($property in $settings.PSObject.Properties) {
            if ($property.Name -notmatch '^FAIRMADE_[A-Z_]+$' -or $property.Value -isnot [string]) {
                throw 'Local settings must contain only string-valued FAIRMADE_ environment settings.'
            }
            $previous[$property.Name] = [Environment]::GetEnvironmentVariable($property.Name, 'Process')
            [Environment]::SetEnvironmentVariable($property.Name, $property.Value, 'Process')
        }
        $python = Join-Path $RuntimeRoot 'venv/Scripts/python.exe'
        $backendArgs = @('-m', 'uvicorn', 'fairmade.main:app', '--app-dir', ('"' + (Join-Path $release 'backend/src') + '"'), '--host', '127.0.0.1', '--port', '8000', '--no-access-log')
        $backend = Start-Process -FilePath $python -ArgumentList $backendArgs -WorkingDirectory (Join-Path $release 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $RuntimeRoot 'logs/backend.out.log') -RedirectStandardError (Join-Path $RuntimeRoot 'logs/backend.err.log')
    } finally {
        foreach ($key in $previous.Keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
    }
    # Frontend is launched only after server-only settings have been removed from this process.
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $vite = Join-Path $release 'frontend/node_modules/vite/bin/vite.js'
    $frontend = Start-Process -FilePath $node -ArgumentList @(('"' + $vite + '"'), '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory (Join-Path $release 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $RuntimeRoot 'logs/frontend.out.log') -RedirectStandardError (Join-Path $RuntimeRoot 'logs/frontend.err.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        try {
            $null = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 1
            $null = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 1
            $ready = $true
            break
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'Runtime startup failed. Inspect logs locally; settings and database were retained.' }
    $records = @{}
    foreach ($entry in @(@{ name = 'backend'; process = $backend }, @{ name = 'frontend'; process = $frontend })) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($entry.process.Id)"
        if (-not $process) { throw 'A runtime process exited during startup.' }
        $records[$entry.name] = @{ pid = $process.ProcessId; executable = $process.ExecutablePath; created = $process.CreationDate.ToUniversalTime().ToString('o') }
    }
    $records | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
} catch {
    foreach ($process in @($frontend, $backend)) {
        if ($process -and -not $process.HasExited) { Stop-RuntimeProcess $process.Id }
    }
    throw
}
Write-Output "Frontend: http://127.0.0.1:5173/ ; API: http://127.0.0.1:8000/docs ; revision: $($current.commit)"
