[CmdletBinding()]
param(
    [string]$Repository = (Split-Path $PSScriptRoot -Parent),
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'FairMade/runtime'),
    [string]$Revision = 'origin/main',
    [string]$PythonExecutable = 'python',
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = 'Stop'
$Repository = (Resolve-Path -LiteralPath $Repository).ProviderPath
$RuntimeRoot = [IO.Path]::GetFullPath($RuntimeRoot)
$trees = @(git -C $Repository worktree list --porcelain | Where-Object { $_.StartsWith('worktree ') })
if ($LASTEXITCODE -ne 0) { throw 'Repository is not a Git checkout.' }
foreach ($tree in $trees) {
    $path = [IO.Path]::GetFullPath($tree.Substring(9))
    if ($RuntimeRoot.Equals($path, [StringComparison]::OrdinalIgnoreCase) -or
        $RuntimeRoot.StartsWith($path + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The runtime must be outside every Git checkout.'
    }
}
$statePath = Join-Path $RuntimeRoot 'processes.json'
if (Test-Path -LiteralPath $statePath) {
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    foreach ($service in @($state.backend, $state.frontend)) {
        if ($service -and (Get-Process -Id $service.pid -ErrorAction SilentlyContinue)) {
            throw 'Stop the managed runtime before initializing or changing its revision.'
        }
    }
}
$commit = git -C $Repository rev-parse --verify "$Revision^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the requested revision.' }
$release = Join-Path $RuntimeRoot "releases/$commit"
$frontendTools = Join-Path $RuntimeRoot 'dependencies/frontend'
$venv = Join-Path $RuntimeRoot 'venv'
$privateRoot = Join-Path $RuntimeRoot 'private'
foreach ($path in @($RuntimeRoot, $frontendTools, $privateRoot, (Join-Path $RuntimeRoot 'data'), (Join-Path $RuntimeRoot 'logs'))) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls.exe $privateRoot /inheritance:r /grant:r "*$($sid):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict access to private local settings.' }
if (-not (Test-Path -LiteralPath $release)) {
    $archive = Join-Path $RuntimeRoot "snapshot-$commit.zip"
    git -C $Repository archive --format=zip "--output=$archive" $commit
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot export failed.' }
    Expand-Archive -LiteralPath $archive -DestinationPath $release
    Remove-Item -LiteralPath $archive
}
$frontend = Join-Path $release 'frontend'
$lockHash = (Get-FileHash -LiteralPath (Join-Path $frontend 'package-lock.json')).Hash
$installedLockPath = Join-Path $frontendTools 'installed-lock.sha256'
if ($SkipDependencyInstall -and (-not (Test-Path -LiteralPath $installedLockPath) -or
    (Get-Content -LiteralPath $installedLockPath -Raw).Trim() -ne $lockHash)) {
    throw 'Cannot skip dependency installation when the prepared frontend lockfile does not match.'
}
if (-not $SkipDependencyInstall) {
    if (-not (Test-Path -LiteralPath $installedLockPath) -or
        (Get-Content -LiteralPath $installedLockPath -Raw).Trim() -ne $lockHash) {
        Copy-Item -LiteralPath (Join-Path $frontend 'package.json') -Destination $frontendTools
        Copy-Item -LiteralPath (Join-Path $frontend 'package-lock.json') -Destination $frontendTools
        & npm.cmd ci --prefix $frontendTools
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts/python.exe'))) {
        & $PythonExecutable -m venv $venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    & (Join-Path $venv 'Scripts/python.exe') -m pip install -e "$(Join-Path $release 'backend')[dev]"
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
$python = Join-Path $venv 'Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python) -or
    -not (Test-Path -LiteralPath (Join-Path $frontendTools 'node_modules/vite/bin/vite.js'))) {
    throw 'Dependencies are missing. Do not skip installation on a fresh machine.'
}
$lockHash | Set-Content -LiteralPath $installedLockPath -Encoding ASCII
$linkPath = Join-Path $frontend 'node_modules'
if (-not (Test-Path -LiteralPath $linkPath)) {
    New-Item -ItemType Junction -Path $linkPath -Target (Join-Path $frontendTools 'node_modules') | Out-Null
} else {
    $link = Get-Item -LiteralPath $linkPath -Force
    $target = [IO.Path]::GetFullPath((Join-Path $frontendTools 'node_modules'))
    if ($link.LinkType -ne 'Junction' -or @($link.Target).Count -ne 1 -or
        -not ([IO.Path]::GetFullPath($link.Target[0])).Equals($target, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The release has an unexpected dependency directory. Preserve it and inspect locally.'
    }
}
$configPath = Join-Path $privateRoot 'settings.json'
if (-not (Test-Path -LiteralPath $configPath)) {
    $database = (Join-Path $RuntimeRoot 'data/fairmade.sqlite3').Replace('\', '/')
    [ordered]@{
        FAIRMADE_DATABASE_URL = "sqlite:///$database"
        FAIRMADE_CORS_ORIGINS = ''
        FAIRMADE_ASSISTANTS_ENABLED = 'false'
        FAIRMADE_RECEIPTS_ENABLED = 'false'
        FAIRMADE_TESSERACT_PATH = 'C:\Program Files\Tesseract-OCR\tesseract.exe'
        FAIRMADE_PAYPAL_ENABLED = 'false'
        FAIRMADE_PAYPAL_ENVIRONMENT = 'sandbox'
        FAIRMADE_PAYPAL_SANDBOX_CLIENT_ID = ''
        FAIRMADE_PAYPAL_SANDBOX_CLIENT_SECRET = ''
        FAIRMADE_PAYPAL_SANDBOX_MERCHANT_ID = ''
    } | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding UTF8
}
$settings = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$oldDatabase = [Environment]::GetEnvironmentVariable('FAIRMADE_DATABASE_URL', 'Process')
$oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
try {
    $env:FAIRMADE_DATABASE_URL = $settings.FAIRMADE_DATABASE_URL
    $env:PYTHONPATH = Join-Path $release 'backend/src'
    Push-Location (Join-Path $release 'backend')
    try {
        & $python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { throw 'Database migration failed. Preserve the database and inspect the error.' }
    } finally { Pop-Location }
} finally {
    [Environment]::SetEnvironmentVariable('FAIRMADE_DATABASE_URL', $oldDatabase, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $oldPythonPath, 'Process')
}
[ordered]@{ commit = $commit; release = $release; repository = $Repository } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'current.json') -Encoding UTF8
Write-Output "Runtime initialized from $commit at $RuntimeRoot. Private settings were preserved."
