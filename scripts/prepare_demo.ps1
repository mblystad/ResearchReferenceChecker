param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $PSScriptRoot)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ first."
    exit 1
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (.venv)..."
    python -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"

Write-Host "Installing project dependencies..."
& $py -m pip install -e .

Write-Host "Building abbreviation datasets and enriched registry..."
& $py scripts\build_journal_abbreviation_db.py

if (-not $SkipTests) {
    Write-Host "Running tests..."
    & $py -m pytest -q
}

Write-Host ""
Write-Host "Demo preparation complete."
Write-Host "Launch app with:"
Write-Host "  .\.venv\Scripts\python.exe run_app.py"
