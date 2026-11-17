"""Treina o modelo de previsão de falta e gera as evidências de avaliação.

Uso:
  python scripts/treinar.py                 # usa data/raw/KaggleV2-May-2016.csv se existir; senão, a base sintética
  python scripts/treinar.py --sintetico     # força a base sintética
Saídas: modelos/modelo_falta.joblib, modelos/modelo_falta.json e evidencias/modelo_*.{json,md,png}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.metrics import precision_recall_curve, roc_curve  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from vagacerta import config  # noqa: E402
from vagacerta.dados import montar_atributos, preparar_base, separar_por_tempo  # noqa: E402
from vagacerta.modelo import avaliar_por_grupo, treinar  # noqa: E402

NOMES = {"baseline_taxa_media": "Baseline (taxa média)", "regressao_logistica": "Regressão logística",
         "gradient_boosting": "Gradient boosting"}


def escolher_base(forcar_sintetico: bool) -> tuple[Path, str]:
    if not forcar_sintetico and config.CSV_KAGGLE.exists():
        return config.CSV_KAGGLE, "kaggle_medical_appointment_no_shows_vitoria_2016"
    if not config.CSV_SINTETICO.exists():
        subprocess.run([sys.executable, str(RAIZ / "scripts" / "gerar_sintetico.py")], check=True)
    print("ATENÇÃO: usando base SINTÉTICA. As métricas não representam o mundo real.")
    return config.CSV_SINTETICO, "sintetica"


def graficos(modelo, teste, dir_saida: Path) -> list[dict]:
    x, y = montar_atributos(teste), teste["faltou"].to_numpy()
    prob = modelo.probabilidade(x)

    fig, eixos = plt.subplots(1, 3, figsize=(15, 4.2))
    fpr, tpr, _ = roc_curve(y, prob)
    eixos[0].plot(fpr, tpr, color="#1f6feb")
    eixos[0].plot([0, 1], [0, 1], "--", color="#999")
    eixos[0].set(title=f"Curva ROC (AUC {modelo.metadados['metricas_teste']['roc_auc']})",
                 xlabel="Falsos positivos", ylabel="Faltas detectadas (recall)")
    prec, rec, _ = precision_recall_curve(y, prob)
    eixos[1].plot(rec, prec, color="#1f6feb")
    eixos[1].axhline(y.mean(), ls="--", color="#999", label="taxa de falta (acaso)")
    eixos[1].set(title=f"Precisão x Recall (PR-AUC {modelo.metadados['metricas_teste']['pr_auc']})",
                 xlabel="Recall", ylabel="Precisão")
    eixos[1].legend()
    # Curva de ganho: se reforçarmos o lembrete das X% consultas de maior risco, que fração das faltas cobrimos?
    ordem = np.argsort(-prob)
    ganho = np.cumsum(y[ordem]) / max(y.sum(), 1)
    frac = np.arange(1, len(y) + 1) / len(y)
    eixos[2].plot(frac, ganho, color="#1f6feb", label="modelo")
    eixos[2].plot([0, 1], [0, 1], "--", color="#999", label="sem modelo (aleatório)")
    eixos[2].axvline(0.30, color="#d29922", ls=":", label="capacidade de reforço (30%)")
    eixos[2].set(title="Curva de ganho", xlabel="Fração das consultas contatadas", ylabel="Fração das faltas cobertas")
    eixos[2].legend()
    fig.tight_layout()
    fig.savefig(dir_saida / "modelo_curvas.png", dpi=130)
    plt.close(fig)

    amostra = teste.sample(min(8000, len(teste)), random_state=0)
    imp = permutation_importance(modelo.estimador, montar_atributos(amostra), amostra["faltou"].to_numpy(),
                                 scoring="average_precision", n_repeats=5, random_state=0)
    tabela = sorted(
        ({"atributo": a, "importancia": round(float(m), 4), "desvio": round(float(s), 4)}
         for a, m, s in zip(x.columns, imp.importances_mean, imp.importances_std)),
        key=lambda r: -r["importancia"],
    )
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh([r["atributo"] for r in tabela][::-1], [r["importancia"] for r in tabela][::-1], color="#1f6feb")
    ax.set(title="Importância por permutação (queda no PR-AUC)", xlabel="Queda no PR-AUC")
    fig.tight_layout()
    fig.savefig(dir_saida / "modelo_importancia.png", dpi=130)
    plt.close(fig)
    return tabela


def relatorio_md(meta, comparacao, grupos, importancia, origem) -> str:
    def linha(nome, m):
        return (f"| {NOMES.get(nome, nome)} | {m['roc_auc']} | {m['pr_auc']} | {m['recall']} | "
                f"{m['precisao']} | {m['f1']} | {m['brier']} |")

    t = meta["metricas_teste"]
    mc = t["matriz_confusao"]
    partes = [
        "# Avaliação do modelo de previsão de falta",
        "",
        f"Gerado por `scripts/treinar.py` em {meta['treinado_em']}. Base: **{origem}**.",
        "",
    ]
    if origem == "sintetica":
        partes += ["> **Base sintética.** Estes números só mostram que o pipeline funciona. "
                   "Para o resultado real, coloque o CSV do Kaggle em `data/raw/` e rode de novo.", ""]
    partes += [
        "## Divisão temporal",
        "",
        "Treino no passado, validação e teste no futuro, como seria em produção.",
        "",
        "| Conjunto | Período | Consultas |",
        "|---|---|---|",
        *[f"| {k} | {v[0]} a {v[1]} | {meta['tamanhos'][k]} |" for k, v in meta["periodos"].items()],
        "",
        "## Comparação no conjunto de teste",
        "",
        f"Limiar escolhido na validação para sinalizar as {int(meta['capacidade_reforco'] * 100)}% "
        "consultas de maior risco (capacidade de reforço da equipe). No teste, como a distribuição muda de uma "
        f"semana para outra, o mesmo limiar sinalizou {t['fracao_sinalizada']:.0%}.",
        "",
        "| Modelo | ROC-AUC | PR-AUC | Recall | Precisão | F1 | Brier |",
        "|---|---|---|---|---|---|---|",
        *[linha(n, m) for n, m in comparacao["teste"].items()],
        "",
        f"Modelo escolhido (maior PR-AUC na validação): **{NOMES.get(meta['modelo'], meta['modelo'])}**.",
        "",
        "### Como ler",
        "",
        f"- Taxa real de falta no teste: {t['taxa_falta_real']:.1%}.",
        f"- Contatando {t['fracao_sinalizada']:.0%} das consultas (as de maior risco), o modelo cobre "
        f"**{t['recall']:.0%} das faltas**. Sem modelo, contatar {t['fracao_sinalizada']:.0%} ao acaso cobriria "
        f"cerca de {t['fracao_sinalizada']:.0%}.",
        f"- Entre as consultas sinalizadas, {t['precisao']:.0%} de fato faltaram "
        f"(contra {t['taxa_falta_real']:.0%} na média).",
        f"- Matriz de confusão: VP {mc['vp']}, FP {mc['fp']}, FN {mc['fn']}, VN {mc['vn']}.",
        "- Priorizamos **recall** e **PR-AUC** porque a classe de interesse (falta) é minoritária e "
        "deixar de avisar quem vai faltar custa mais do que um lembrete a mais.",
        "",
        "![curvas](modelo_curvas.png)",
        "",
        "## Importância dos atributos",
        "",
        "| Atributo | Queda no PR-AUC |",
        "|---|---|",
        *[f"| {r['atributo']} | {r['importancia']} ± {r['desvio']} |" for r in importancia],
        "",
        "![importancia](modelo_importancia.png)",
        "",
        "## Comportamento por grupo (uso responsável)",
        "",
        "O modelo só decide **a intensidade do lembrete**, nunca o acesso à consulta. Mesmo assim, conferimos "
        "se algum grupo é sinalizado de forma muito diferente da sua taxa real de falta.",
        "",
        "Duas políticas no mesmo modelo:",
        "",
        "- **limiar único**: as consultas de maior risco no geral;",
        f"- **cota mínima por faixa etária**: além disso, em cada faixa as {meta['cota_minima_faixa']:.0%} "
        "de maior risco da própria faixa recebem reforço (limiares calibrados na validação). **É a política em uso na API.**",
        "",
        "| Grupo | Consultas | Taxa real de falta | Sinalizada (único) | Recall (único) | Sinalizada (cota) | Recall (cota) |",
        "|---|---|---|---|---|---|---|",
    ]
    fmt = lambda v: f"{v:.1%}" if v is not None else "-"  # noqa: E731
    for dim, valores in grupos.items():
        for g, v in valores.items():
            partes.append(f"| {dim}: {g} | {v['n']} | {v['taxa_falta_real']:.1%} | {fmt(v['fracao_sinalizada'])} | "
                          f"{fmt(v['recall'])} | {fmt(v['fracao_sinalizada_cota'])} | {fmt(v['recall_cota'])} |")
    c = meta["metricas_teste_com_cota"]
    partes += [
        "",
        f"No total, com a cota: sinaliza {c['fracao_sinalizada']:.1%} das consultas, recall {c['recall']:.1%}, "
        f"precisão {c['precisao']:.1%} (limiar único: {t['fracao_sinalizada']:.1%}, {t['recall']:.1%}, "
        f"{t['precisao']:.1%}).",
    ]
    return "\n".join(partes) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sintetico", action="store_true")
    a = p.parse_args()

    caminho, origem = escolher_base(a.sintetico)
    df = preparar_base(caminho)
    treino, validacao, teste = separar_por_tempo(df)
    print(f"Base {origem}: {len(df)} consultas | treino {len(treino)} | validação {len(validacao)} | teste {len(teste)}")

    modelo, comparacao = treinar(treino, validacao, teste, origem)
    modelo.salvar()

    config.DIR_EVIDENCIAS.mkdir(exist_ok=True)
    grupos = avaliar_por_grupo(modelo, teste)
    importancia = graficos(modelo, teste, config.DIR_EVIDENCIAS)
    (config.DIR_EVIDENCIAS / "modelo_metricas.json").write_text(
        json.dumps({"metadados": modelo.metadados, "comparacao": comparacao, "por_grupo": grupos,
                    "importancia": importancia}, indent=2, ensure_ascii=False), encoding="utf-8")
    (config.DIR_EVIDENCIAS / "modelo_avaliacao.md").write_text(
        relatorio_md(modelo.metadados, comparacao, grupos, importancia, origem), encoding="utf-8")

    t = modelo.metadados["metricas_teste"]
    print(f"Modelo escolhido: {modelo.nome} | teste ROC-AUC {t['roc_auc']} | PR-AUC {t['pr_auc']} | "
          f"recall {t['recall']} contatando {t['fracao_sinalizada']:.0%}")
    print(f"Evidências em {config.DIR_EVIDENCIAS}")


if __name__ == "__main__":
    main()
