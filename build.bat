@echo off
setlocal

cd /d %~dp0

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ first.
  exit /b 1
)

set PYTHONUTF8=1

echo Installing build dependencies...
python -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

echo Building executable with PyInstaller spec...
python -m PyInstaller --clean ReferenceChecker.spec
if errorlevel 1 exit /b 1

if not exist "dist\ReferenceChecker.exe" (
  echo Build failed: dist\ReferenceChecker.exe not found.
  exit /b 1
)

if exist "dist\release" rmdir /s /q "dist\release"
mkdir "dist\release"
copy /Y "dist\ReferenceChecker.exe" "dist\release\ReferenceChecker.exe" >nul
copy /Y "RELEASE_README.txt" "dist\release\README.txt" >nul

powershell -NoProfile -Command ^
  "if (Test-Path 'dist/ReferenceChecker-windows-x64.zip') { Remove-Item 'dist/ReferenceChecker-windows-x64.zip' -Force }; Compress-Archive -Path 'dist/release/*' -DestinationPath 'dist/ReferenceChecker-windows-x64.zip'"
if errorlevel 1 exit /b 1

echo.
echo Release package created:
echo   dist\ReferenceChecker-windows-x64.zip
