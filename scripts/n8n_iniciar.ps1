# Sobe o n8n com o workflow do Vaga Certa importado e publicado.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/n8n_iniciar.ps1 [-GeminiFalso] [-Porta 5678]
param(
    [switch]$GeminiFalso,  # aponta o workflow para tests/gemini_falso.py (teste sem chave)
    [int]$Porta = 5678
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot

# 1. Variáveis do .env (GEMINI_API_KEY, GEMINI_MODELO, VAGACERTA_N8N_TOKEN...)
$arquivoEnv = Join-Path $raiz ".env"
if (Test-Path $arquivoEnv) {
    foreach ($linha in Get-Content $arquivoEnv -Encoding UTF8) {
        if ($linha -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            Set-Item -Path ("env:" + $Matches[1]) -Value $Matches[2]
        }
    }
} else {
    Write-Warning "Sem .env: copie .env.example para .env e preencha GEMINI_API_KEY e VAGACERTA_N8N_TOKEN."
}

if ($GeminiFalso) {
    $env:GEMINI_BASE_URL = "http://127.0.0.1:8790"
    if (-not $env:GEMINI_API_KEY) { $env:GEMINI_API_KEY = "chave-de-teste" }
    Write-Host "Modo teste: o workflow vai chamar o Gemini falso em $env:GEMINI_BASE_URL"
} elseif (-not $env:GEMINI_API_KEY) {
    Write-Warning "GEMINI_API_KEY vazia: o workflow vai responder erro e o Vaga Certa usará o template."
}

# 2. Configuração do n8n
$env:N8N_USER_FOLDER = Join-Path $raiz "n8n\.local"
$env:N8N_PORT = "$Porta"
$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"   # o workflow lê chave e token das variáveis de ambiente
$env:N8N_DIAGNOSTICS_ENABLED = "false"
$env:N8N_PERSONALIZATION_ENABLED = "false"
$env:N8N_VERSION_NOTIFICATIONS_ENABLED = "false"
$env:GENERIC_TIMEZONE = "America/Sao_Paulo"

# 3. Importa e publica o workflow (idempotente: reimporta a versão do Git a cada início)
$workflow = Join-Path $raiz "n8n\vagacerta-mensagem.json"
n8n import:workflow --input="$workflow"
if ($LASTEXITCODE -ne 0) { throw "falha ao importar o workflow" }
n8n publish:workflow --id=VagaCertaMsg0001
if ($LASTEXITCODE -ne 0) { throw "falha ao publicar o workflow" }

# 4. Sobe o n8n (Ctrl+C para parar)
Write-Host "n8n em http://localhost:$Porta  |  webhook: http://localhost:$Porta/webhook/vagacerta-mensagem"
n8n start
