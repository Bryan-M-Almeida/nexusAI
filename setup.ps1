# Prepares a development environment: virtualenv + dependencies.
# Usage:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Ollama nao encontrado. Instale em https://ollama.com/download e depois rode:" -ForegroundColor Yellow
    Write-Host "  ollama pull qwen3:8b" -ForegroundColor Yellow
}
Write-Host "Pronto. Inicie com: .\.venv\Scripts\python run_nexus.py" -ForegroundColor Cyan
