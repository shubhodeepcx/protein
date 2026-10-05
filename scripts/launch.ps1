<#
.SYNOPSIS
    Launches ProteoLens (backend + frontend) in production mode and opens a browser.

.DESCRIPTION
    One command to run the whole app. It is idempotent: first run sets up the
    Python virtualenv, installs npm packages, and builds the frontend; later
    runs skip whatever is already in place and start in a few seconds.

    Production mode is deliberate. `next dev` overlays a floating dev-tools
    bubble on every page, which has no place in a demo -- `next start` serves
    the compiled build and shows nothing but the app.

.PARAMETER Rebuild
    Force a fresh production build even if .next already exists. Use after
    changing frontend source.

.PARAMETER NoBrowser
    Start the servers but do not open a browser window.

.EXAMPLE
    .\scripts\launch.ps1
    .\scripts\launch.ps1 -Rebuild
#>
[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$Root     = Split-Path -Parent $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPy   = Join-Path $Backend '.venv\Scripts\python.exe'

$BackendPort  = 8000
$FrontendPort = 3000
$FrontendUrl  = "http://localhost:$FrontendPort"

# Processes we start ourselves, so shutdown only kills what we own.
$script:Started = @()

function Write-Step   { param([string]$m) Write-Host "==> $m" -ForegroundColor Cyan }
function Write-Ok     { param([string]$m) Write-Host "    $m" -ForegroundColor Green }
function Write-Warn   { param([string]$m) Write-Host "    $m" -ForegroundColor Yellow }

function Test-Port {
    param([int]$Port)
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $c
}

function Wait-ForHttp {
    param([string]$Url, [int]$TimeoutSec = 90, [string]$Label)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { return $true }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    throw "$Label did not become ready at $Url within $TimeoutSec seconds."
}

function Stop-Started {
    if ($script:Started.Count -eq 0) { return }
    Write-Host ''
    Write-Step 'Shutting down'
    foreach ($p in $script:Started) {
        if ($p -and -not $p.HasExited) {
            try {
                # Kill the whole tree: `npm start` spawns next-server as a child.
                & taskkill.exe /PID $p.Id /T /F *> $null
            } catch { }
        }
    }
    Write-Ok 'Servers stopped.'
    $script:Started = @()
}

try {
    Write-Host ''
    Write-Host '  ProteoLens' -ForegroundColor White
    Write-Host '  Protein structure visualization' -ForegroundColor DarkGray
    Write-Host ''

    # ---- preflight -------------------------------------------------------
    if (Test-Port $BackendPort) {
        throw "Port $BackendPort is already in use. Close whatever is running there (an earlier launch?) and try again."
    }
    if (Test-Port $FrontendPort) {
        throw "Port $FrontendPort is already in use. Close whatever is running there (an earlier launch?) and try again."
    }

    # ---- backend setup ---------------------------------------------------
    if (-not (Test-Path $VenvPy)) {
        Write-Step 'Creating the Python virtualenv (first run only, ~1 min)'
        Push-Location $Backend
        try {
            python -m venv .venv
            & $VenvPy -m pip install --quiet --upgrade pip
            & $VenvPy -m pip install --quiet -e ".[dev]"
        } finally { Pop-Location }
        Write-Ok 'Backend dependencies installed.'
    } else {
        Write-Ok 'Backend dependencies present.'
    }

    # ---- frontend setup --------------------------------------------------
    if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
        Write-Step 'Installing npm packages (first run only, a few minutes)'
        Push-Location $Frontend
        try { npm install --no-fund --no-audit } finally { Pop-Location }
        Write-Ok 'Frontend dependencies installed.'
    } else {
        Write-Ok 'Frontend dependencies present.'
    }

    $needsBuild = $Rebuild -or -not (Test-Path (Join-Path $Frontend '.next\BUILD_ID'))
    if ($needsBuild) {
        Write-Step 'Building the frontend for production (~30s)'
        Push-Location $Frontend
        try {
            npm run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed. Fix the errors above and re-run.' }
        } finally { Pop-Location }
        Write-Ok 'Build complete.'
    } else {
        Write-Ok 'Production build present (pass -Rebuild to force a fresh one).'
    }

    # ---- start servers ---------------------------------------------------
    Write-Step "Starting the API on port $BackendPort"
    $env:CORS_ORIGINS = $FrontendUrl
    $script:Started += Start-Process -FilePath $VenvPy `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', "$BackendPort" `
        -WorkingDirectory $Backend -PassThru -WindowStyle Hidden
    Wait-ForHttp -Url "http://localhost:$BackendPort/health" -Label 'API' | Out-Null
    Write-Ok "API ready at http://localhost:$BackendPort (docs at /docs)"

    Write-Step "Starting the web app on port $FrontendPort"
    $script:Started += Start-Process -FilePath 'cmd.exe' `
        -ArgumentList '/c', 'npm', 'run', 'start' `
        -WorkingDirectory $Frontend -PassThru -WindowStyle Hidden
    Wait-ForHttp -Url $FrontendUrl -Label 'Web app' | Out-Null
    Write-Ok "Web app ready at $FrontendUrl"

    if (-not $NoBrowser) { Start-Process $FrontendUrl }

    Write-Host ''
    Write-Host "  ProteoLens is running -> $FrontendUrl" -ForegroundColor Green
    Write-Host '  Press Ctrl+C to stop both servers.' -ForegroundColor DarkGray
    Write-Host ''

    # Idle until interrupted; the finally block does the cleanup.
    while ($true) { Start-Sleep -Seconds 3600 }
}
catch {
    Write-Host ''
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ''
    exit 1
}
finally {
    Stop-Started
}
