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

function Write-Dev([string]$Message, [string]$Color = "Cyan") {
    Write-Host "[dev] $Message" -ForegroundColor $Color
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
    if (-not (Test-Path (Join-Path $ProjectRoot ".venv"))) {
        Write-Dev "Backend dependencies are missing; running uv sync..."
        uv sync
    }
    if (-not (Test-Path (Join-Path $DashboardDir "node_modules"))) {
        Write-Dev "Frontend dependencies are missing; running pnpm install..."
        Push-Location $DashboardDir
        pnpm install
        Pop-Location
    }
}

# -- Reserve free ports; listeners stay open until both servers have started,
# mirroring the race-prevention strategy in dev.sh. -------------
function Reserve-Port([int]$StartPort) {
    $candidate = $StartPort
    while ($candidate -le 65535) {
        $listener = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Any, $candidate)
        try {
            $listener.Start()
            return $listener
        } catch {
            $listener.Server.Close()
            $candidate++
        }
    }
    throw "No free port found at or above $StartPort"
}

$backendListener = Reserve-Port $BackendPort
$frontendListener = Reserve-Port $FrontendPort
$BackendPort = ([System.Net.IPEndPoint]$backendListener.LocalEndpoint).Port
$FrontendPort = ([System.Net.IPEndPoint]$frontendListener.LocalEndpoint).Port

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
$errorPattern = '(?i)\bERROR\b|\bCRITICAL\b|Traceback'

$backend = New-Object System.Diagnostics.Process
$backend.StartInfo.FileName = "uv"
$backend.StartInfo.Arguments = "run main.py"
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
# cmd.exe resolves pnpm.cmd from PATH (CreateProcess cannot do that on its own).
$frontend = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "pnpm dev" `
    -WorkingDirectory $DashboardDir -NoNewWindow -PassThru

# Both processes have bound their ports; release the reservations.
$backendListener.Stop()
$frontendListener.Stop()

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

    # Stop both servers as soon as either process exits.
    while (-not $backend.HasExited -and -not $frontend.HasExited) {
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
        Write-Dev "Frontend exited; stopping the backend." Red
    }
    exit $exitStatus
} finally {
    Write-Dev "Stopping development servers..."
    Stop-Tree $frontend
    Stop-Tree $backend
    Start-Sleep -Milliseconds 300
    Write-Dev "Development servers stopped." Green
}
