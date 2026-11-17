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

    def probabilidade(self, x: pd.DataFrame) -> np.ndarray:
        return self.estimador.predict_proba(x[ATRIBUTOS])[:, 1]

    def faixa(self, prob: float) -> str:
        if prob >= self.limiar_alto:
            return "alto"
        if prob >= self.limiar_medio:
            return "medio"
        return "baixo"

    def prever(self, linhas_brutas: pd.DataFrame) -> list[dict]:
        x = montar_atributos(linhas_brutas)
        probs = self.probabilidade(x)
        saida = []
        for (_, linha), p in zip(x.iterrows(), probs):
            saida.append({
                "probabilidade_falta": round(float(p), 4),
                "faixa_risco": self.faixa(float(p)),
                "sinais": sinais_de_risco(linha),
            })
        return saida

    def salvar(self) -> None:
        config.DIR_MODELOS.mkdir(parents=True, exist_ok=True)
        joblib.dump({"estimador": self.estimador, "nome": self.nome,
                     "limiar_alto": self.limiar_alto, "limiar_medio": self.limiar_medio},
                    config.ARQ_MODELO)
        config.ARQ_METADADOS.write_text(json.dumps(self.metadados, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def carregar(cls) -> "ModeloFalta":
        if not config.ARQ_MODELO.exists():
            raise FileNotFoundError("Modelo não treinado. Rode: python scripts/treinar.py")
        d = joblib.load(config.ARQ_MODELO)
        meta = json.loads(config.ARQ_METADADOS.read_text(encoding="utf-8")) if config.ARQ_METADADOS.exists() else {}
        return cls(d["estimador"], d["nome"], d["limiar_alto"], d["limiar_medio"], meta)


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
    }
    return ModeloFalta(est, escolhido, limiar_alto, limiar_medio, meta), relatorio


def avaliar_por_grupo(modelo: ModeloFalta, teste: pd.DataFrame) -> dict:
    """Recall e taxa de sinalização por gênero e faixa etária: verifica se o modelo trata grupos de forma desigual."""
    x = montar_atributos(teste)
    prob = modelo.probabilidade(x)
    df = pd.DataFrame({
        "y": teste["faltou"].to_numpy(),
        "pred": (prob >= modelo.limiar_alto).astype(int),
        "genero": np.where(x["genero_f"] == 1, "F", "M"),
        "faixa_etaria": pd.cut(x["idade"], [-1, 11, 17, 29, 59, 200],
                               labels=["0-11", "12-17", "18-29", "30-59", "60+"]).astype(str),
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
            }
    return saida
