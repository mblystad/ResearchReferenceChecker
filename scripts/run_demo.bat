@echo off
setlocal

cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
  echo Environment not found. Running prepare_demo.ps1 first...
  powershell -ExecutionPolicy Bypass -File ".\scripts\prepare_demo.ps1"
  if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" run_app.py
