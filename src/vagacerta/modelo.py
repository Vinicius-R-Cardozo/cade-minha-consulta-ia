"""Modelo de Machine Learning que estima a probabilidade de o paciente faltar à consulta.

Uso no produto: o gestor (regulador) vê as consultas ordenadas por risco e decide onde reforçar
o lembrete (ligação, WhatsApp) e onde preparar encaixe. O modelo NÃO nega atendimento a ninguém.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import config
from .dados import ATRIBUTOS, montar_atributos

# Fração das consultas que a equipe consegue contatar com lembrete reforçado.
# O limiar de "risco alto" é escolhido para caber nessa capacidade.
CAPACIDADE_REFORCO = 0.30

# Cota mínima por faixa etária: em cada faixa, pelo menos esta fração das consultas de maior risco
# DA PRÓPRIA FAIXA recebe reforço. Sem isso, o limiar único quase não alcança idosos (ver evidencias).
COTA_MINIMA_FAIXA = 0.15
FAIXAS_ETARIAS = [(-1, 11, "0-11"), (11, 17, "12-17"), (17, 29, "18-29"), (29, 59, "30-59"), (59, 200, "60+")]


def faixa_etaria(idades) -> np.ndarray:
    idades = np.asarray(idades, dtype=float)
    saida = np.empty(len(idades), dtype=object)
    for ini, fim, nome in FAIXAS_ETARIAS:
        saida[(idades > ini) & (idades <= fim)] = nome
    return saida


def candidatos() -> dict:
    return {
        "baseline_taxa_media": DummyClassifier(strategy="prior"),
        "regressao_logistica": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")
        ),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50,
            class_weight="balanced", random_state=42,
        ),
    }


def metricas(y: np.ndarray, prob: np.ndarray, limiar: float) -> dict:
    pred = (prob >= limiar).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)),
        "taxa_falta_real": round(float(y.mean()), 4),
        "roc_auc": round(float(roc_auc_score(y, prob)), 4) if len(set(y)) > 1 else None,
        "pr_auc": round(float(average_precision_score(y, prob)), 4),
        "brier": round(float(brier_score_loss(y, prob)), 4),
        "limiar": round(float(limiar), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "precisao": round(float(precision_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "fracao_sinalizada": round(float(pred.mean()), 4),
        "matriz_confusao": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }


def limiar_por_capacidade(prob: np.ndarray, capacidade: float = CAPACIDADE_REFORCO) -> float:
    """Limiar que sinaliza só a fração `capacidade` de consultas com maior risco."""
    return float(np.quantile(prob, 1 - capacidade))


@dataclass
class ModeloFalta:
    estimador: object
    nome: str
    limiar_alto: float
    limiar_medio: float
    metadados: dict = field(default_factory=dict)
    limiares_faixa: dict = field(default_factory=dict)  # limiar de "alto" por faixa etária (cota mínima)

    def probabilidade(self, x: pd.DataFrame) -> np.ndarray:
        return self.estimador.predict_proba(x[ATRIBUTOS])[:, 1]

    def limiar_para(self, idade: float) -> float:
        return self.limiares_faixa.get(faixa_etaria([idade])[0], self.limiar_alto)

    def sinalizar(self, x: pd.DataFrame, prob: np.ndarray, com_cota: bool = True) -> np.ndarray:
        """True = recebe lembrete reforçado."""
        if not com_cota:
            return prob >= self.limiar_alto
        limiares = np.array([self.limiar_para(i) for i in x["idade"]])
        return prob >= limiares

    def faixa(self, prob: float, idade: float | None = None) -> str:
        limiar = self.limiar_para(idade) if idade is not None else self.limiar_alto
        if prob >= limiar:
            return "alto"
        if prob >= min(self.limiar_medio, limiar):
            return "medio"
        return "baixo"

    def prever(self, linhas_brutas: pd.DataFrame) -> list[dict]:
        x = montar_atributos(linhas_brutas)
        probs = self.probabilidade(x)
        saida = []
        for (_, linha), p in zip(x.iterrows(), probs):
            saida.append({
                "probabilidade_falta": round(float(p), 4),
                "faixa_risco": self.faixa(float(p), float(linha["idade"])),
                "sinais": sinais_de_risco(linha),
            })
        return saida

    def salvar(self) -> None:
        config.DIR_MODELOS.mkdir(parents=True, exist_ok=True)
        joblib.dump({"estimador": self.estimador, "nome": self.nome, "limiar_alto": self.limiar_alto,
                     "limiar_medio": self.limiar_medio, "limiares_faixa": self.limiares_faixa},
                    config.ARQ_MODELO)
        config.ARQ_METADADOS.write_text(json.dumps(self.metadados, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def carregar(cls) -> "ModeloFalta":
        if not config.ARQ_MODELO.exists():
            raise FileNotFoundError("Modelo não treinado. Rode: python scripts/treinar.py")
        d = joblib.load(config.ARQ_MODELO)
        meta = json.loads(config.ARQ_METADADOS.read_text(encoding="utf-8")) if config.ARQ_METADADOS.exists() else {}
        return cls(d["estimador"], d["nome"], d["limiar_alto"], d["limiar_medio"], meta, d.get("limiares_faixa", {}))


def sinais_de_risco(linha: pd.Series) -> list[str]:
    """Explicação simples, em linguagem do gestor, dos fatores que mais pesam no modelo."""
    sinais = []
    if linha["faltas_anteriores"] > 0:
        sinais.append(f"faltou {int(linha['faltas_anteriores'])}x antes")
    if linha["dias_antecedencia"] >= 15:
        sinais.append(f"agendada com {int(linha['dias_antecedencia'])} dias de antecedência")
    if 12 <= linha["idade"] <= 30:
        sinais.append("faixa etária com mais faltas (12 a 30 anos)")
    if linha["alcoolismo"] == 1:
        sinais.append("condição associada a mais faltas")
    if linha["mesmo_dia"] == 1:
        sinais.append("consulta marcada para o mesmo dia (risco menor)")
    return sinais


def treinar(treino: pd.DataFrame, validacao: pd.DataFrame, teste: pd.DataFrame, origem: str) -> tuple[ModeloFalta, dict]:
    """Treina os candidatos, escolhe pelo PR-AUC na validação e mede uma única vez no teste."""
    x_tr, y_tr = montar_atributos(treino), treino["faltou"].to_numpy()
    x_va, y_va = montar_atributos(validacao), validacao["faltou"].to_numpy()
    x_te, y_te = montar_atributos(teste), teste["faltou"].to_numpy()

    relatorio = {"validacao": {}, "teste": {}}
    ajustados = {}
    for nome, est in candidatos().items():
        est.fit(x_tr, y_tr)
        prob_va = est.predict_proba(x_va)[:, 1]
        limiar = limiar_por_capacidade(prob_va)
        relatorio["validacao"][nome] = metricas(y_va, prob_va, limiar)
        ajustados[nome] = (est, limiar)

    escolhido = max(
        (n for n in ajustados if n != "baseline_taxa_media"),
        key=lambda n: relatorio["validacao"][n]["pr_auc"],
    )

    # Teste: todos os candidatos, com o limiar escolhido na validação (o teste não influencia nada).
    for nome, (est, limiar) in ajustados.items():
        relatorio["teste"][nome] = metricas(y_te, est.predict_proba(x_te)[:, 1], limiar)

    est, limiar_alto = ajustados[escolhido]
    prob_va = est.predict_proba(x_va)[:, 1]
    limiar_medio = float(np.quantile(prob_va, 0.40))  # 40% de menor risco ficam em "baixo"

    # Cota mínima por faixa etária, calibrada na validação (o teste continua sem influenciar nada).
    faixas_va = faixa_etaria(x_va["idade"])
    limiares_faixa = {
        g: min(limiar_alto, float(np.quantile(prob_va[faixas_va == g], 1 - COTA_MINIMA_FAIXA)))
        for g in np.unique(faixas_va)
    }
    modelo = ModeloFalta(est, escolhido, limiar_alto, limiar_medio, {}, limiares_faixa)
    prob_te = modelo.probabilidade(x_te)
    flag_cota = modelo.sinalizar(x_te, prob_te, com_cota=True)
    politica_cota = {
        "fracao_sinalizada": round(float(flag_cota.mean()), 4),
        "recall": round(float(flag_cota[y_te == 1].mean()), 4),
        "precisao": round(float(y_te[flag_cota].mean()), 4) if flag_cota.any() else None,
    }

    meta = {
        "modelo": escolhido,
        "treinado_em": date.today().isoformat(),
        "origem_dados": origem,
        "atributos": ATRIBUTOS,
        "capacidade_reforco": CAPACIDADE_REFORCO,
        "limiar_alto": round(limiar_alto, 4),
        "limiar_medio": round(limiar_medio, 4),
        "tamanhos": {"treino": len(treino), "validacao": len(validacao), "teste": len(teste)},
        "periodos": {
            "treino": [str(treino["data_consulta"].min().date()), str(treino["data_consulta"].max().date())],
            "validacao": [str(validacao["data_consulta"].min().date()), str(validacao["data_consulta"].max().date())],
            "teste": [str(teste["data_consulta"].min().date()), str(teste["data_consulta"].max().date())],
        },
        "metricas_teste": relatorio["teste"][escolhido],
        "cota_minima_faixa": COTA_MINIMA_FAIXA,
        "limiares_faixa": limiares_faixa,
        "metricas_teste_com_cota": politica_cota,
    }
    modelo.metadados = meta
    return modelo, relatorio


def avaliar_por_grupo(modelo: ModeloFalta, teste: pd.DataFrame) -> dict:
    """Recall e taxa de sinalização por gênero e faixa etária, com limiar único e com cota mínima por faixa."""
    x = montar_atributos(teste)
    prob = modelo.probabilidade(x)
    df = pd.DataFrame({
        "y": teste["faltou"].to_numpy(),
        "pred": modelo.sinalizar(x, prob, com_cota=False).astype(int),
        "pred_cota": modelo.sinalizar(x, prob, com_cota=True).astype(int),
        "genero": np.where(x["genero_f"] == 1, "F", "M"),
        "faixa_etaria": faixa_etaria(x["idade"]),
    })
    saida = {}
    for col in ["genero", "faixa_etaria"]:
        saida[col] = {}
        for grupo, g in df.groupby(col):
            faltas = g[g["y"] == 1]
            saida[col][grupo] = {
                "n": int(len(g)),
                "taxa_falta_real": round(float(g["y"].mean()), 4),
                "fracao_sinalizada": round(float(g["pred"].mean()), 4),
                "recall": round(float(faltas["pred"].mean()), 4) if len(faltas) else None,
                "fracao_sinalizada_cota": round(float(g["pred_cota"].mean()), 4),
                "recall_cota": round(float(faltas["pred_cota"].mean()), 4) if len(faltas) else None,
            }
    return saida
