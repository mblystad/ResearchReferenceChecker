param(
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Environment not found. Running prepare_demo first..."
    & ".\scripts\prepare_demo.ps1"
}

$py = ".\.venv\Scripts\python.exe"
if ($NoLaunch) {
    Write-Host "Environment is ready."
    Write-Host "Launch command:"
    Write-Host "  $py run_app.py"
    exit 0
}

& $py run_app.py
