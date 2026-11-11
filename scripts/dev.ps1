# --------------------------------------------------------------
# dev.ps1 - Windows (PowerShell 5.1+) equivalent of scripts/dev.sh.
#
# Backend: starts from port 6185 and uses the next available port.
# Frontend: starts from port 3007 and proxies API requests to the selected backend.
#
# Usage (from the repository root):
#   .\dev.cmd
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\dev.ps1 -BackendPort 7000 -FrontendPort 4000
#   $env:SKIP_INSTALL = "1"  before launching to skip dependency installation.
#                        (DEV_BACKEND_PORT / DEV_FRONTEND_PORT env vars also work.)
#
# Console output policy:
#   Backend log lines are hidden except credential lines (Username / Initial
#   password, shown in green) and error lines (shown in red). The full backend
#   log is written to logs\dev-backend.log. Frontend (Vite) output is shown as-is.
# --------------------------------------------------------------
[CmdletBinding()]
param(
    [int]$BackendPort = $(if ($env:DEV_BACKEND_PORT) { [int]$env:DEV_BACKEND_PORT } else { 6185 }),
    [int]$FrontendPort = $(if ($env:DEV_FRONTEND_PORT) { [int]$env:DEV_FRONTEND_PORT } else { 3007 })
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DashboardDir = Join-Path $ProjectRoot "dashboard"
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendRequiredFiles = @(
    (Join-Path $DashboardDir "node_modules\.bin\vite.cmd"),
    (Join-Path $DashboardDir "node_modules\@mdi\font\css\materialdesignicons.css"),
    (Join-Path $DashboardDir "node_modules\@mdi\font\fonts\materialdesignicons-webfont.ttf"),
    (Join-Path $DashboardDir "node_modules\subset-font\package.json")
)

# Keep uv's cache inside the project on Windows. This avoids failures caused by
# an inaccessible or malformed per-user cache directory.
if (-not $env:UV_CACHE_DIR) {
    $env:UV_CACHE_DIR = Join-Path $ProjectRoot ".uv-cache"
}
if (-not $env:UV_PYTHON_INSTALL_DIR) {
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $ProjectRoot ".uv-python"
}

function Write-Dev([string]$Message, [string]$Color = "Cyan") {
    Write-Host "[dev] $Message" -ForegroundColor $Color
}

function Get-MissingFrontendDependencies {
    return @($FrontendRequiredFiles | Where-Object {
        -not (Test-Path -LiteralPath $_ -PathType Leaf)
    })
}

Set-Location $ProjectRoot

# UTF-8 console so backend output (which may contain non-ASCII) decodes correctly.
chcp 65001 > $null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# -- Validate executables before either server starts ----------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Dev "uv is unavailable. Install it with: winget install astral-sh.uv" Red
    exit 1
}
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    Write-Dev "pnpm is unavailable. Install it with: npm install -g pnpm@10" Red
    exit 1
}

# -- Install dependencies on the first run ($env:SKIP_INSTALL="1" skips) --
if ($env:SKIP_INSTALL -ne "1") {
    $backendEnvReady = $false
    if (Test-Path $BackendPython) {
        & $BackendPython -c "import sys" 2>$null
        $backendEnvReady = ($LASTEXITCODE -eq 0)
    }
    if (-not $backendEnvReady) {
        Write-Dev "Backend environment is missing or invalid; running uv sync..."
        uv sync
        if ($LASTEXITCODE -ne 0) {
            Write-Dev "uv sync failed; backend cannot be started." Red
            exit $LASTEXITCODE
        }
    }
    $missingFrontendDependencies = @(Get-MissingFrontendDependencies)
    if ($missingFrontendDependencies.Count -gt 0) {
        Write-Dev "Frontend dependencies are missing or incomplete; running pnpm install..."
        Push-Location $DashboardDir
        try {
            pnpm install
            $pnpmInstallExitCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($pnpmInstallExitCode -ne 0) {
            Write-Dev "pnpm install failed; frontend cannot be started." Red
            exit $pnpmInstallExitCode
        }
    }
}

# Validate the files needed by the development command even when installation
# was explicitly skipped. A partially populated node_modules directory is not
# sufficient: the MDI subset step needs the package CSS and TTF at startup.
$missingFrontendDependencies = @(Get-MissingFrontendDependencies)
if ($missingFrontendDependencies.Count -gt 0) {
    Write-Dev "Frontend dependencies are still incomplete. Missing files:" Red
    foreach ($missingFile in $missingFrontendDependencies) {
        Write-Dev "  $missingFile" Red
    }
    Write-Dev "Run 'pnpm install' in the dashboard directory, or unset SKIP_INSTALL." Red
    exit 1
}

# -- Pick free backend/frontend ports. Ports are probed via Get-NetTCPConnection
# only: holding an actual listener socket would leak its handle into the
# backend child process (CreateProcess inherits handles when output is
# redirected), keeping the port busy even after the listener is closed. --
function Find-FreePort([int]$StartPort) {
    $candidate = $StartPort
    while ($candidate -le 65535) {
        $inUse = Get-NetTCPConnection -LocalPort $candidate -State Listen -ErrorAction SilentlyContinue
        if (-not $inUse) { return $candidate }
        $candidate++
    }
    throw "No free port found at or above $StartPort"
}

$BackendPort = Find-FreePort $BackendPort
$FrontendPort = Find-FreePort $FrontendPort

# Environment variables consumed by main.py (backend) and vite.config.ts (frontend).
$env:DASHBOARD_PORT = "$BackendPort"
$env:LIBSCLAW_DEV_BACKEND_PORT = "$BackendPort"
$env:LIBSCLAW_DEV_FRONTEND_PORT = "$FrontendPort"

# -- Backend: redirect output, show only credential/error lines --
$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$BackendLog = Join-Path $LogDir "dev-backend.log"
Set-Content -Path $BackendLog -Value ""

# Credential banner printed by astrbot/dashboard/server.py:
#   "->  Username: ..." / "->  Initial password: ..." (English keywords on purpose:
#   keeping this file pure ASCII avoids encoding issues on Windows PowerShell 5.1,
#   which assumes ANSI for BOM-less scripts).
$credentialPattern = '(?i)username|password'
# Substring match on purpose: bare \bERROR\b would hide exception lines like
# "ModuleNotFoundError: ..." that follow a Traceback header.
$errorPattern = '(?i)error|exception|traceback|critical'

$backend = New-Object System.Diagnostics.Process
$backend.StartInfo.FileName = $BackendPython
$backend.StartInfo.Arguments = "main.py"
$backend.StartInfo.WorkingDirectory = $ProjectRoot
$backend.StartInfo.UseShellExecute = $false
$backend.StartInfo.RedirectStandardOutput = $true
$backend.StartInfo.RedirectStandardError = $true
$backend.StartInfo.CreateNoWindow = $true
$backend.StartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$backend.StartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

$onBackendLine = {
    $line = $Event.SourceEventArgs.Data
    if ($null -eq $line) { return }
    Add-Content -Path $Event.MessageData.LogPath -Value $line
    if ($line -match $Event.MessageData.CredentialPattern) {
        Write-Host $line -ForegroundColor Green
    } elseif ($line -match $Event.MessageData.ErrorPattern) {
        Write-Host $line -ForegroundColor Red
    }
}
$eventData = @{
    LogPath = $BackendLog
    CredentialPattern = $credentialPattern
    ErrorPattern = $errorPattern
}
Register-ObjectEvent -InputObject $backend -EventName OutputDataReceived -Action $onBackendLine -MessageData $eventData | Out-Null
Register-ObjectEvent -InputObject $backend -EventName ErrorDataReceived -Action $onBackendLine -MessageData $eventData | Out-Null

$backend.Start() | Out-Null
$backend.BeginOutputReadLine()
$backend.BeginErrorReadLine()

# -- Frontend: Vite inherits the console so its output is shown as-is --
# Use the already installed local executables. This avoids an interactive pnpm
# modules-store migration prompt while retaining package.json's MDI subset step.
# Large SFCs plus frequent HMR can exhaust Node's default heap and make Vite
# exit silently; raise the limit unless the user already configured it.
if (-not $env:NODE_OPTIONS) {
    $env:NODE_OPTIONS = "--max-old-space-size=8192"
}
$frontendCommand = "node scripts\subset-mdi-font.mjs && node_modules\.bin\vite.cmd --host"
$frontendRestartCommand = "node_modules\.bin\vite.cmd --host"
$FrontendRestartLimit = 10
$frontendRestarts = 0
function Start-Frontend([string]$Command) {
    return Start-Process -FilePath "cmd.exe" -ArgumentList "/d", "/c", $Command `
        -WorkingDirectory $DashboardDir -NoNewWindow -PassThru
}
$frontend = Start-Frontend $frontendCommand

function Stop-Tree($proc) {
    if ($proc -and -not $proc.HasExited) {
        # /T kills the whole process tree so uv/node children never leak.
        cmd /c "taskkill /PID $($proc.Id) /T /F >nul 2>&1"
    }
}

try {
    Write-Host ""
    Write-Dev "Backend port: $BackendPort (full log: logs\dev-backend.log)"
    Write-Dev "Frontend port: $FrontendPort"
    Write-Dev "Press Ctrl+C to stop both."
    Write-Host ""

    # Restart Vite if it dies unexpectedly; stop both only when the backend
    # exits or Vite keeps crashing.
    while (-not $backend.HasExited) {
        if ($frontend.HasExited) {
            $frontendExitCode = $frontend.ExitCode
            if ($frontendRestarts -ge $FrontendRestartLimit) { break }
            $frontendRestarts++
            Write-Dev "Frontend exited with status $frontendExitCode; restarting ($frontendRestarts/$FrontendRestartLimit)..." Yellow
            Start-Sleep -Seconds 2
            $frontend = Start-Frontend $frontendRestartCommand
        }
        Start-Sleep -Milliseconds 500
    }

    $exitStatus = 0
    if ($backend.HasExited) {
        if ($backend.ExitCode -ne 0) {
            $exitStatus = $backend.ExitCode
            Write-Dev "Backend exited with status $exitStatus; stopping the frontend." Red
            Write-Dev "Backend output was hidden; see logs\dev-backend.log to debug." Red
        } else {
            Write-Dev "Backend exited; stopping the frontend." Red
        }
    } else {
        $exitStatus = 1
        Write-Dev "Frontend exited $FrontendRestartLimit times (last status $($frontend.ExitCode)); stopping the backend." Red
    }
    exit $exitStatus
} finally {
    Write-Dev "Stopping development servers..."
    Stop-Tree $frontend
    Stop-Tree $backend
    Start-Sleep -Milliseconds 300
    Write-Dev "Development servers stopped." Green
}
