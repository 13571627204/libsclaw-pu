@echo off
rem Windows one-command launcher for LibsClaw development servers.
rem Equivalent of: ./scripts/dev.sh (macOS / Linux)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %*
