@echo off
setlocal

cd /d %~dp0

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ first.
  exit /b 1
)

set PYTHONUTF8=1

python -m PyInstaller ^
  --name "ReferenceChecker" ^
  --onefile ^
  --noconsole ^
  --add-data "app.py;." ^
  --add-data "src;src" ^
  --add-data "predatory_db_v7_with_norwegian_levels.csv;." ^
  --add-data "data;data" ^
  --collect-all streamlit ^
  --clean ^
  run_app.py
