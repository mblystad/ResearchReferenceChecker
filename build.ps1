$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ first."
    exit 1
}

$env:PYTHONUTF8 = "1"

python -m PyInstaller `
  --name "ReferenceChecker" `
  --onefile `
  --noconsole `
  --add-data "app.py;." `
  --add-data "src;src" `
  --add-data "predatory_db_v7_with_norwegian_levels.csv;." `
  --add-data "data;data" `
  --collect-all streamlit `
  --clean `
  run_app.py
