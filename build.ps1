# Builds a standalone Windows app in dist\NEXUS\NEXUS.exe (no Python needed on the target PC).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

.\.venv\Scripts\python -m pip install pyinstaller
.\.venv\Scripts\python -m PyInstaller --noconfirm --windowed --name NEXUS `
    --add-data "nexus\web;nexus\web" `
    --add-data "nexus\seed;nexus\seed" `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-submodules webview `
    --hidden-import pyttsx3.drivers.sapi5 `
    --collect-submodules comtypes `
    run_nexus.py

Write-Host "Build pronto: dist\NEXUS\NEXUS.exe (os dados do usuario ficam em %LOCALAPPDATA%\NEXUS)" -ForegroundColor Cyan
