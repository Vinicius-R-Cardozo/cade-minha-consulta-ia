"""Configuração central. Tudo que é segredo vem de variável de ambiente (.env), nunca do código."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

DIR_DADOS = RAIZ / "data"
CSV_KAGGLE = DIR_DADOS / "KaggleV2-May-2016.csv"
CSV_SINTETICO = DIR_DADOS / "sintetico" / "consultas_sinteticas.csv"
DIR_BASE_CONHECIMENTO = RAIZ / "base_conhecimento"
DIR_MODELOS = RAIZ / "modelos"
DIR_EVIDENCIAS = RAIZ / "evidencias"

ARQ_MODELO = DIR_MODELOS / "modelo_falta.joblib"
ARQ_METADADOS = DIR_MODELOS / "modelo_falta.json"

# IA generativa: workflow do n8n que chama o Google Gemini. A chave do Gemini fica no n8n, não aqui.
# Se o n8n estiver desligado ou falhar, o sistema usa o gerador de modelo fixo (template).
IA_MODO = os.getenv("CADE_IA", "n8n")  # "n8n" ou "desligada"
N8N_WEBHOOK_URL = os.getenv("CADE_N8N_WEBHOOK_URL", "http://localhost:5678/webhook/cade-minha-consulta-mensagem")
N8N_TOKEN = os.getenv("CADE_N8N_TOKEN", "")
N8N_TIMEOUT_S = float(os.getenv("CADE_N8N_TIMEOUT_S", "50"))

# Token para o backend Java chamar este serviço. Vazio = sem exigência (só para desenvolvimento).
TOKEN_SERVICO = os.getenv("CADE_TOKEN_SERVICO", "")


def ia_ligada() -> bool:
    return IA_MODO == "n8n" and bool(N8N_WEBHOOK_URL)
