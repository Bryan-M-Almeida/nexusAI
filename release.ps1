# Everything a release needs, in dist\release:
#   NEXUS-Setup-<version>.exe               full installer (Inno Setup)
#   NEXUS-update-<version>-base<N>.zip      small update for installed copies (+ .sha256)
# Usage:  powershell -ExecutionPolicy Bypass -File release.ps1 [-SkipBuild]
param([switch]$SkipBuild)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $SkipBuild) {
    & .\build.ps1
    if ($LASTEXITCODE -ne 0) { throw "build.ps1 falhou" }
}
$version = (& .\.venv\Scripts\python -c "from nexus import __version__; print(__version__)").Trim()
New-Item -ItemType Directory -Force dist\release | Out-Null

& .\.venv\Scripts\python build_update.py dist\NEXUS dist\release
if ($LASTEXITCODE -ne 0) { throw "build_update.py falhou" }

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 nao encontrado (winget install JRSoftware.InnoSetup)" }
& $iscc /Q "/DAppVersion=$version" installer\nexus.iss
if ($LASTEXITCODE -ne 0) { throw "ISCC falhou (codigo $LASTEXITCODE)" }

Get-ChildItem dist\release -Filter "*$version*" | ForEach-Object {
    "{0,-45} {1,8:N1} MB" -f $_.Name, ($_.Length / 1MB)
}
