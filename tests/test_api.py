from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from vagacerta import api, config
from vagacerta.geracao import Orquestrador


@pytest.fixture()
def cliente(modelo_treinado, monkeypatch):
    modelo, _ = modelo_treinado
    monkeypatch.setattr(config, "TOKEN_SERVICO", "")
    api.modelo.cache_clear()
    api.orquestrador.cache_clear()
    monkeypatch.setattr(api, "modelo", lambda: modelo)
    monkeypatch.setattr(api, "orquestrador", lambda: Orquestrador(usar_ia=False))
    return TestClient(api.app)


def corpo_risco(**extra):
    hoje = date.today()
    return {"idade": 25, "genero": "M", "data_agendamento": str(hoje),
            "data_consulta": str(hoje + timedelta(days=30)), "consultas_anteriores": 3,
            "faltas_anteriores": 2, **extra}


def test_health(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["base_conhecimento_docs"] >= 10
    assert r.json()["ia_generativa"].startswith("desligada")


def test_risco_ok(cliente):
    r = cliente.post("/v1/risco-falta", json=corpo_risco(consulta_id="abc"))
    assert r.status_code == 200
    d = r.json()
    assert d["consulta_id"] == "abc"
    assert 0 <= d["probabilidade_falta"] <= 1
    assert d["faixa_risco"] in {"baixo", "medio", "alto"}
    assert d["recomendacao"]


def test_risco_lote(cliente):
    r = cliente.post("/v1/risco-falta/lote", json={"consultas": [corpo_risco(), corpo_risco(idade=80)]})
    assert r.status_code == 200 and len(r.json()) == 2


@pytest.mark.parametrize("extra", [
    {"idade": -3},
    {"genero": "X"},
    {"faltas_anteriores": 9, "consultas_anteriores": 1},
    {"data_consulta": "2020-01-01"},
])
def test_risco_entrada_invalida_retorna_422(cliente, extra):
    assert cliente.post("/v1/risco-falta", json=corpo_risco(**extra)).status_code == 422


def test_lote_vazio_ou_grande_demais(cliente):
    assert cliente.post("/v1/risco-falta/lote", json={"consultas": []}).status_code == 422
    assert cliente.post("/v1/risco-falta/lote", json={"consultas": [corpo_risco()] * 501}).status_code == 422


def test_mensagem_ok(cliente):
    r = cliente.post("/v1/mensagens/confirmacao", json={
        "procedimento": "ENDOSCOPIA DIGESTIVA ALTA", "data_consulta": str(date.today() + timedelta(days=3)),
        "hora": "07:15", "unidade": "Hospital Municipal", "primeiro_nome": "Carlos", "faixa_risco": "alto"})
    assert r.status_code == 200
    d = r.json()
    assert d["sms"].startswith("Olá, Carlos!")
    assert d["fontes"] == ["base_conhecimento/endoscopia.md"]
    assert "acompanhante" in d["app"].lower()


def test_mensagem_de_consulta_passada_e_recusada(cliente):
    r = cliente.post("/v1/mensagens/confirmacao", json={
        "procedimento": "ECG", "data_consulta": str(date.today() - timedelta(days=1)),
        "hora": "07:15", "unidade": "Hospital Municipal"})
    assert r.status_code == 422


def test_mensagem_procedimento_desconhecido_avisa(cliente):
    r = cliente.post("/v1/mensagens/confirmacao", json={
        "procedimento": "CINTILOGRAFIA OSSEA", "data_consulta": str(date.today() + timedelta(days=3)),
        "hora": "10:00", "unidade": "Hospital Municipal"})
    assert r.status_code == 200
    assert r.json()["fontes"] == []
    assert any("nenhuma orientação" in a for a in r.json()["avisos"])


def test_busca_preparo(cliente):
    r = cliente.post("/v1/preparo/buscar", json={"consulta": "mamografia", "k": 2})
    assert r.status_code == 200
    assert r.json()[0]["id"] == "mamografia"


def test_token_de_servico_obrigatorio_quando_configurado(cliente, monkeypatch):
    monkeypatch.setattr(config, "TOKEN_SERVICO", "segredo-de-teste")
    assert cliente.post("/v1/risco-falta", json=corpo_risco()).status_code == 401
    assert cliente.post("/v1/risco-falta", json=corpo_risco(), headers={"X-Service-Token": "errado"}).status_code == 401
    ok = cliente.post("/v1/risco-falta", json=corpo_risco(), headers={"X-Service-Token": "segredo-de-teste"})
    assert ok.status_code == 200
    assert cliente.get("/health").status_code == 200  # health continua aberto para o orquestrador de deploy
