$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ first."
    exit 1
}

$env:PYTHONUTF8 = "1"

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Write-Host "Building executable with PyInstaller spec..."
python -m PyInstaller --clean ReferenceChecker.spec

$distDir = Join-Path (Get-Location) "dist"
$exePath = Join-Path $distDir "ReferenceChecker.exe"
if (-not (Test-Path $exePath)) {
    Write-Error "Build failed: $exePath was not created."
    exit 1
}

$releaseDir = Join-Path $distDir "release"
if (Test-Path $releaseDir) {
    Remove-Item -Recurse -Force $releaseDir
}
New-Item -ItemType Directory -Path $releaseDir | Out-Null

Copy-Item $exePath (Join-Path $releaseDir "ReferenceChecker.exe")
Copy-Item "RELEASE_README.txt" (Join-Path $releaseDir "README.txt")

$zipPath = Join-Path $distDir "ReferenceChecker-windows-x64.zip"
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath

Write-Host ""
Write-Host "Release package created:"
Write-Host "  $zipPath"
