"""Configuração central. Tudo que é segredo vem de variável de ambiente (.env), nunca do código."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

DIR_DADOS = RAIZ / "data"
CSV_KAGGLE = DIR_DADOS / "raw" / "KaggleV2-May-2016.csv"
CSV_SINTETICO = DIR_DADOS / "sintetico" / "consultas_sinteticas.csv"
DIR_BASE_CONHECIMENTO = RAIZ / "base_conhecimento"
DIR_MODELOS = RAIZ / "modelos"
DIR_EVIDENCIAS = RAIZ / "evidencias"

ARQ_MODELO = DIR_MODELOS / "modelo_falta.joblib"
ARQ_METADADOS = DIR_MODELOS / "modelo_falta.json"

# IA generativa (Claude). Sem chave, o sistema usa o gerador de modelo fixo (template).
LLM_MODELO = os.getenv("VAGACERTA_LLM_MODELO", "claude-opus-5-5")
LLM_ESFORCO = os.getenv("VAGACERTA_LLM_ESFORCO", "low")
LLM_FALLBACK_SERVIDOR = os.getenv("VAGACERTA_LLM_FALLBACK_SERVIDOR", "1") == "1"
LLM_TIMEOUT_S = float(os.getenv("VAGACERTA_LLM_TIMEOUT_S", "30"))

# Token para o backend Java chamar este serviço. Vazio = sem exigência (só para desenvolvimento).
TOKEN_SERVICO = os.getenv("VAGACERTA_TOKEN_SERVICO", "")


def tem_credencial_llm() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
