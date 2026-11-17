"""API do serviço de IA do Vaga Certa (FastAPI).

Quem chama: o backend Java (Spring Boot). O app mobile não fala direto com este serviço.
- POST /v1/risco-falta          -> probabilidade de falta e faixa de risco (ML)
- POST /v1/mensagens/confirmacao -> mensagem de confirmação com preparo (RAG + IA generativa)
- POST /v1/preparo/buscar       -> só a parte de recuperação do RAG (útil para depurar e para a tela do app)
- GET  /health                  -> estado do modelo, da base e da IA generativa
"""

from __future__ import annotations

import hmac
from datetime import date, time
from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from . import __version__, config
from .geracao import DadosConsulta, Orquestrador
from .modelo import ModeloFalta
from .rag import BaseConhecimento

app = FastAPI(
    title="Vaga Certa — serviço de IA",
    version=__version__,
    description="Previsão de falta (ML), orientações de preparo (RAG) e mensagens em linguagem simples (IA generativa).",
)


@lru_cache
def modelo() -> ModeloFalta:
    return ModeloFalta.carregar()


@lru_cache
def base() -> BaseConhecimento:
    return BaseConhecimento()


@lru_cache
def orquestrador() -> Orquestrador:
    return Orquestrador()


def exigir_token(x_service_token: str | None = Header(default=None)) -> None:
    """Autenticação serviço-a-serviço. Em produção VAGACERTA_TOKEN_SERVICO é obrigatório."""
    esperado = config.TOKEN_SERVICO
    if esperado and not (x_service_token and hmac.compare_digest(x_service_token, esperado)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de serviço inválido ou ausente")


# ---------- contratos ----------

class EntradaRisco(BaseModel):
    """Só dados necessários para a previsão. Sem nome, CPF, endereço ou telefone (minimização, LGPD)."""
    consulta_id: str | None = Field(default=None, max_length=64, description="ID interno, devolvido como veio")
    idade: int = Field(ge=0, le=110)
    genero: Literal["F", "M"]
    data_agendamento: date
    data_consulta: date
    bolsa_familia: bool = False
    hipertensao: bool = False
    diabetes: bool = False
    alcoolismo: bool = False
    deficiencia: bool = False
    sms_recebido: bool = False
    consultas_anteriores: int = Field(default=0, ge=0, le=1000)
    faltas_anteriores: int = Field(default=0, ge=0, le=1000)

    @model_validator(mode="after")
    def coerente(self):
        if self.data_consulta < self.data_agendamento:
            raise ValueError("data_consulta não pode ser anterior a data_agendamento")
        if self.faltas_anteriores > self.consultas_anteriores:
            raise ValueError("faltas_anteriores não pode ser maior que consultas_anteriores")
        return self


class SaidaRisco(BaseModel):
    consulta_id: str | None
    probabilidade_falta: float
    faixa_risco: Literal["baixo", "medio", "alto"]
    sinais: list[str]
    recomendacao: str
    modelo: str


class EntradaLote(BaseModel):
    consultas: list[EntradaRisco] = Field(min_length=1, max_length=500)


class EntradaMensagem(BaseModel):
    procedimento: str = Field(min_length=3, max_length=120, examples=["Ultrassom de abdome total"])
    data_consulta: date
    hora: time
    unidade: str = Field(min_length=3, max_length=120, examples=["Policlínica Centro"])
    endereco: str = Field(default="", max_length=160)
    primeiro_nome: str | None = Field(default=None, max_length=60, description="Usado só localmente, não vai para a IA")
    faixa_risco: Literal["baixo", "medio", "alto"] = "baixo"


class SaidaMensagem(BaseModel):
    sms: str
    app: str
    gerado_por: str
    fontes: list[str]
    itens_usados: list[str]
    avisos: list[str]
    latencia_ms: int


class EntradaBusca(BaseModel):
    consulta: str = Field(min_length=2, max_length=200)
    k: int = Field(default=2, ge=1, le=5)


RECOMENDACAO = {
    "alto": "Reforçar lembrete (ligação ou WhatsApp) e deixar paciente da fila avisado para possível encaixe.",
    "medio": "Lembrete padrão com pedido de confirmação 72h e 24h antes.",
    "baixo": "Lembrete padrão 48h antes.",
}


def _linha(e: EntradaRisco) -> dict:
    d = e.model_dump()
    d["dias_antecedencia"] = (e.data_consulta - e.data_agendamento).days
    d["data_consulta"] = pd.Timestamp(e.data_consulta)
    return d


def _prever(entradas: list[EntradaRisco]) -> list[SaidaRisco]:
    try:
        m = modelo()
    except FileNotFoundError as err:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(err)) from err
    previsoes = m.prever(pd.DataFrame([_linha(e) for e in entradas]))
    return [
        SaidaRisco(consulta_id=e.consulta_id, recomendacao=RECOMENDACAO[p["faixa_risco"]], modelo=m.nome, **p)
        for e, p in zip(entradas, previsoes)
    ]


# ---------- rotas ----------

@app.get("/health")
def health():
    estado = {"status": "ok", "versao": __version__}
    try:
        m = modelo()
        estado["modelo"] = {"nome": m.nome, "origem_dados": m.metadados.get("origem_dados"),
                            "treinado_em": m.metadados.get("treinado_em")}
    except FileNotFoundError:
        estado["status"] = "degradado"
        estado["modelo"] = None
    estado["base_conhecimento_docs"] = len(base().docs)
    estado["ia_generativa"] = f"n8n + Gemini ({config.N8N_WEBHOOK_URL})" if orquestrador().ia else "desligada (template)"
    return estado


@app.post("/v1/risco-falta", response_model=SaidaRisco, dependencies=[Depends(exigir_token)])
def risco_falta(entrada: EntradaRisco):
    return _prever([entrada])[0]


@app.post("/v1/risco-falta/lote", response_model=list[SaidaRisco], dependencies=[Depends(exigir_token)])
def risco_falta_lote(entrada: EntradaLote):
    return _prever(entrada.consultas)


@app.post("/v1/mensagens/confirmacao", response_model=SaidaMensagem, dependencies=[Depends(exigir_token)])
def mensagem_confirmacao(entrada: EntradaMensagem):
    if entrada.data_consulta < date.today():
        raise HTTPException(422, "consulta já passou")
    resultados = base().buscar(entrada.procedimento, k=1)
    dados = DadosConsulta(entrada.procedimento, entrada.data_consulta, entrada.hora, entrada.unidade,
                          entrada.endereco, entrada.faixa_risco)
    msg = orquestrador().gerar(dados, resultados, entrada.primeiro_nome)
    if not resultados:
        msg.avisos.append("nenhuma orientação de preparo encontrada para este procedimento")
    return SaidaMensagem(**msg.__dict__)


@app.post("/v1/preparo/buscar", dependencies=[Depends(exigir_token)])
def buscar_preparo(entrada: EntradaBusca):
    return [
        {"id": r.documento.id, "titulo": r.documento.titulo, "score": round(r.score, 4),
         "fonte": r.documento.fonte, "secoes": r.documento.secoes}
        for r in base().buscar(entrada.consulta, k=entrada.k)
    ]
