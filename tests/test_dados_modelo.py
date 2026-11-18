import pandas as pd
import pytest

from cademinhaconsulta.dados import adicionar_historico, limpar, montar_atributos, preparar_base, separar_por_tempo


def _bruto(linhas):
    base = {"genero": "F", "idade": 30, "bairro": "X", "bolsa_familia": 0, "hipertensao": 0, "diabetes": 0,
            "alcoolismo": 0, "deficiencia": 0, "sms_recebido": 0, "consulta_id": 1}
    return pd.DataFrame([{**base, **l} for l in linhas])


def test_limpar_descarta_idade_negativa_e_agendamento_depois_da_consulta():
    df = _bruto([
        {"paciente_id": 1, "data_agendamento": "2016-05-01T10:00:00Z", "data_consulta": "2016-05-10T00:00:00Z", "faltou": "No"},
        {"paciente_id": 2, "data_agendamento": "2016-05-01T10:00:00Z", "data_consulta": "2016-05-10T00:00:00Z", "faltou": "Yes", "idade": -1},
        {"paciente_id": 3, "data_agendamento": "2016-05-12T10:00:00Z", "data_consulta": "2016-05-10T00:00:00Z", "faltou": "No"},
    ])
    limpo = limpar(df)
    assert list(limpo["paciente_id"]) == [1]
    assert limpo.loc[0, "dias_antecedencia"] == 9


def test_historico_so_usa_dias_anteriores():
    """Sem vazamento: a falta do próprio dia (ou de outra consulta no mesmo dia) não entra no histórico."""
    df = limpar(_bruto([
        {"paciente_id": 1, "data_agendamento": "2016-05-01T08:00:00Z", "data_consulta": "2016-05-02T00:00:00Z", "faltou": "Yes"},
        {"paciente_id": 1, "data_agendamento": "2016-05-01T08:00:00Z", "data_consulta": "2016-05-09T00:00:00Z", "faltou": "Yes"},
        {"paciente_id": 1, "data_agendamento": "2016-05-01T09:00:00Z", "data_consulta": "2016-05-09T00:00:00Z", "faltou": "No"},
        {"paciente_id": 1, "data_agendamento": "2016-05-01T08:00:00Z", "data_consulta": "2016-05-20T00:00:00Z", "faltou": "No"},
    ]))
    h = adicionar_historico(df).sort_values(["data_consulta", "data_agendamento"]).reset_index(drop=True)
    assert list(h["consultas_anteriores"]) == [0, 1, 1, 3]
    assert list(h["faltas_anteriores"]) == [0, 1, 1, 2]


def test_atributos_tem_colunas_esperadas_e_sem_nulos(base_sintetica):
    df = preparar_base(base_sintetica)
    x = montar_atributos(df)
    assert not x.isna().any().any()
    assert x["taxa_faltas_anteriores"].between(0, 1).all()


def test_divisao_temporal_nao_mistura_periodos(base_sintetica):
    tr, va, te = separar_por_tempo(preparar_base(base_sintetica))
    assert tr["data_consulta"].max() < va["data_consulta"].min()
    assert va["data_consulta"].max() < te["data_consulta"].min()


def test_modelo_supera_baseline(modelo_treinado):
    _, relatorio = modelo_treinado
    t = relatorio["teste"]
    assert t["gradient_boosting"]["pr_auc"] > t["baseline_taxa_media"]["pr_auc"]
    assert t["regressao_logistica"]["roc_auc"] > 0.6


def test_previsao_faixas_e_sinais(modelo_treinado):
    modelo, _ = modelo_treinado
    linhas = pd.DataFrame([
        {"idade": 22, "genero": "M", "dias_antecedencia": 40, "data_consulta": pd.Timestamp("2026-11-20"),
         "bolsa_familia": 1, "hipertensao": 0, "diabetes": 0, "alcoolismo": 0, "deficiencia": 0,
         "sms_recebido": 0, "consultas_anteriores": 4, "faltas_anteriores": 3},
        {"idade": 70, "genero": "F", "dias_antecedencia": 0, "data_consulta": pd.Timestamp("2026-11-20"),
         "bolsa_familia": 0, "hipertensao": 1, "diabetes": 0, "alcoolismo": 0, "deficiencia": 0,
         "sms_recebido": 0, "consultas_anteriores": 4, "faltas_anteriores": 0},
    ])
    alto, baixo = modelo.prever(linhas)
    assert alto["probabilidade_falta"] > baixo["probabilidade_falta"]
    assert alto["faixa_risco"] in {"alto", "medio"}
    assert any("faltou 3x" in s for s in alto["sinais"])


def test_cota_por_faixa_so_acrescenta_sinalizacoes(modelo_treinado, base_sintetica):
    modelo, _ = modelo_treinado
    assert modelo.limiares_faixa
    assert all(lim <= modelo.limiar_alto for lim in modelo.limiares_faixa.values())
    x = montar_atributos(preparar_base(base_sintetica))
    prob = modelo.probabilidade(x)
    unico, cota = modelo.sinalizar(x, prob, com_cota=False), modelo.sinalizar(x, prob, com_cota=True)
    assert (cota | ~unico).all()  # todo sinalizado pelo limiar único continua sinalizado com a cota


def test_carregar_sem_modelo_da_erro_claro(tmp_path, monkeypatch):
    from cademinhaconsulta import config
    from cademinhaconsulta.modelo import ModeloFalta

    monkeypatch.setattr(config, "ARQ_MODELO", tmp_path / "nao_existe.joblib")
    with pytest.raises(FileNotFoundError, match="treinar.py"):
        ModeloFalta.carregar()
