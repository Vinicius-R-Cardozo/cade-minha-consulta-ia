# Sobe a API do Cadê Minha Consulta (FastAPI) em http://localhost:8000 — documentação interativa em /docs.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/api_iniciar.ps1 [-Porta 8000]
param([int]$Porta = 8000)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Crie o ambiente antes: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt" }
Write-Host "API em http://localhost:$Porta  |  Swagger: http://localhost:$Porta/docs"
& $python -m uvicorn cademinhaconsulta.api:app --app-dir (Join-Path $raiz "src") --port $Porta
