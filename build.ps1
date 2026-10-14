# Builds a standalone Windows app in dist\NEXUS\NEXUS.exe (no Python needed on the target PC).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1 [-DistPath dist]
#         (use another -DistPath while an older NEXUS.exe from dist\ is still open)
param([string]$DistPath = "dist")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

.\.venv\Scripts\python -m pip install pyinstaller
.\.venv\Scripts\python -m PyInstaller --noconfirm --windowed --name NEXUS --distpath $DistPath `
    --add-data "nexus\web;nexus\web" `
    --add-data "nexus\seed;nexus\seed" `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all onnxruntime `
    --collect-submodules webview `
    --collect-submodules comtypes `
    run_nexus.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou (codigo $LASTEXITCODE). Feche o NEXUS.exe aberto a partir de $DistPath ou use -DistPath." }

Write-Host "Build pronto: $DistPath\NEXUS\NEXUS.exe (os dados do usuario ficam em %LOCALAPPDATA%\NEXUS)" -ForegroundColor Cyan
