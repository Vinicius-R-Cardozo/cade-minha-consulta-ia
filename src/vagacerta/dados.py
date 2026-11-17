"""Leitura, limpeza e engenharia de atributos da base de consultas.

Base principal: "Medical Appointment No Shows" (Kaggle), ~110 mil consultas da rede pública de Vitória (ES), 2016.
A base sintética (scripts/gerar_sintetico.py) tem o mesmo formato e serve para testes e para rodar sem a base real.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Nomes originais do Kaggle (com os erros de grafia da base) -> nomes do projeto
COLUNAS = {
    "PatientId": "paciente_id",
    "AppointmentID": "consulta_id",
    "Gender": "genero",
    "ScheduledDay": "data_agendamento",
    "AppointmentDay": "data_consulta",
    "Age": "idade",
    "Neighbourhood": "bairro",
    "Scholarship": "bolsa_familia",
    "Hipertension": "hipertensao",
    "Diabetes": "diabetes",
    "Alcoholism": "alcoolismo",
    "Handcap": "deficiencia",
    "SMS_received": "sms_recebido",
    "No-show": "faltou",
}

ATRIBUTOS = [
    "idade",
    "genero_f",
    "dias_antecedencia",
    "mesmo_dia",
    "dia_semana",
    "bolsa_familia",
    "hipertensao",
    "diabetes",
    "alcoolismo",
    "deficiencia",
    "sms_recebido",
    "consultas_anteriores",
    "faltas_anteriores",
    "taxa_faltas_anteriores",
]


def carregar_csv(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    faltando = set(COLUNAS) - set(df.columns)
    if faltando:
        raise ValueError(f"CSV sem as colunas esperadas: {sorted(faltando)}")
    return df.rename(columns=COLUNAS)[list(COLUNAS.values())]


def limpar(df: pd.DataFrame) -> pd.DataFrame:
    """Converte tipos e descarta registros impossíveis. Retorna cópia."""
    df = df.copy()
    df["data_agendamento"] = pd.to_datetime(df["data_agendamento"], utc=True).dt.tz_localize(None)
    df["data_consulta"] = pd.to_datetime(df["data_consulta"], utc=True).dt.tz_localize(None).dt.normalize()
    df["faltou"] = (df["faltou"].astype(str).str.strip().str.lower() == "yes").astype(int)
    df["deficiencia"] = (df["deficiencia"] > 0).astype(int)

    df["dias_antecedencia"] = (df["data_consulta"] - df["data_agendamento"].dt.normalize()).dt.days
    validos = (df["idade"].between(0, 110)) & (df["dias_antecedencia"] >= 0)
    return df.loc[validos].reset_index(drop=True)


def adicionar_historico(df: pd.DataFrame) -> pd.DataFrame:
    """Conta consultas e faltas do mesmo paciente em DIAS ANTERIORES à consulta.

    Só olha para o passado: consultas no mesmo dia não entram, porque o resultado delas
    ainda não é conhecido no momento da previsão. Isso evita vazamento de dados.
    """
    df = df.copy()
    por_dia = (
        df.groupby(["paciente_id", "data_consulta"])["faltou"]
        .agg(consultas_dia="size", faltas_dia="sum")
        .reset_index()
        .sort_values(["paciente_id", "data_consulta"])
    )
    grupo = por_dia.groupby("paciente_id")
    por_dia["consultas_anteriores"] = grupo["consultas_dia"].cumsum() - por_dia["consultas_dia"]
    por_dia["faltas_anteriores"] = grupo["faltas_dia"].cumsum() - por_dia["faltas_dia"]

    df = df.merge(
        por_dia[["paciente_id", "data_consulta", "consultas_anteriores", "faltas_anteriores"]],
        on=["paciente_id", "data_consulta"],
        how="left",
    )
    return df


def montar_atributos(df: pd.DataFrame) -> pd.DataFrame:
    """Recebe linhas com os campos brutos (nomes do projeto) e devolve só as colunas de ATRIBUTOS."""
    x = pd.DataFrame(index=df.index)
    x["idade"] = df["idade"].astype(float)
    x["genero_f"] = (df["genero"].astype(str).str.upper() == "F").astype(int)
    x["dias_antecedencia"] = df["dias_antecedencia"].clip(lower=0).astype(float)
    x["mesmo_dia"] = (df["dias_antecedencia"] == 0).astype(int)
    x["dia_semana"] = pd.to_datetime(df["data_consulta"]).dt.day_of_week.astype(int)
    for col in ["bolsa_familia", "hipertensao", "diabetes", "alcoolismo", "deficiencia", "sms_recebido"]:
        x[col] = df[col].astype(int).clip(0, 1)
    x["consultas_anteriores"] = df["consultas_anteriores"].fillna(0).astype(float)
    x["faltas_anteriores"] = df["faltas_anteriores"].fillna(0).astype(float)
    x["taxa_faltas_anteriores"] = np.where(
        x["consultas_anteriores"] > 0, x["faltas_anteriores"] / x["consultas_anteriores"].replace(0, 1), 0.0
    )
    return x[ATRIBUTOS]


def preparar_base(caminho: Path) -> pd.DataFrame:
    """Pipeline completo: CSV -> base limpa com histórico, ordenada por data da consulta."""
    df = adicionar_historico(limpar(carregar_csv(caminho)))
    return df.sort_values(["data_consulta", "data_agendamento"]).reset_index(drop=True)


def separar_por_tempo(df: pd.DataFrame, frac_teste: float = 0.2, frac_validacao: float = 0.15):
    """Divisão temporal: treina no passado, valida e testa no futuro (como seria em produção)."""
    datas = np.sort(df["data_consulta"].unique())
    corte_teste = datas[int(len(datas) * (1 - frac_teste))]
    corte_val = datas[int(len(datas) * (1 - frac_teste - frac_validacao))]
    treino = df[df["data_consulta"] < corte_val]
    validacao = df[(df["data_consulta"] >= corte_val) & (df["data_consulta"] < corte_teste)]
    teste = df[df["data_consulta"] >= corte_teste]
    return treino, validacao, teste
