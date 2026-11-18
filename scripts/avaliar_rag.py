"""Avalia a recuperação do RAG com nomes de procedimento como chegam da regulação (abreviados, maiúsculos, com erro).

Métricas: acerto@1, acerto@3, MRR e, para procedimentos que NÃO estão na base, a taxa de "não encontrado" correta
(o sistema não pode mandar preparo de outro exame). Também varre o limiar mínimo de score para justificar o valor.
Saída: evidencias/rag_avaliacao.md e evidencias/rag_avaliacao.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from cademinhaconsulta import config  # noqa: E402
from cademinhaconsulta.rag import SCORE_MINIMO, BaseConhecimento  # noqa: E402

# (texto da busca, id esperado) — None = não existe orientação na base, o certo é não devolver nada.
# CALIBRACAO: usado para escolher o limiar e ajustar os termos dos documentos.
CASOS_CALIBRACAO = [
    ("ULTRASSONOGRAFIA DE ABDOMEN TOTAL", "ultrassom-abdome"),
    ("usg abdome superior", "ultrassom-abdome"),
    ("ultrasom do figado", "ultrassom-abdome"),
    ("ULTRASSONOGRAFIA PELVICA (GINECOLOGICA)", "ultrassom-pelvico-rins"),
    ("ultrassom de rins e vias urinarias", "ultrassom-pelvico-rins"),
    ("ULTRASSONOGRAFIA DE PROSTATA VIA ABDOMINAL", "ultrassom-pelvico-rins"),
    ("ENDOSCOPIA DIGESTIVA ALTA", "endoscopia"),
    ("endoscopia", "endoscopia"),
    ("COLONOSCOPIA (COLOSCOPIA)", "colonoscopia"),
    ("colono", "colonoscopia"),
    ("ELETROCARDIOGRAMA", "eletrocardiograma"),
    ("ECG", "eletrocardiograma"),
    ("TESTE DE ESFORCO / TESTE ERGOMETRICO", "teste-ergometrico"),
    ("ECOCARDIOGRAFIA TRANSTORACICA", "ecocardiograma"),
    ("ecocardiograma", "ecocardiograma"),
    ("MAMOGRAFIA BILATERAL PARA RASTREAMENTO", "mamografia"),
    ("mamografia", "mamografia"),
    ("RADIOGRAFIA DE TORAX (PA E PERFIL)", "raio-x"),
    ("raio x joelho", "raio-x"),
    ("DOSAGEM DE GLICOSE", "glicemia-jejum"),
    ("glicemia de jejum", "glicemia-jejum"),
    ("DOSAGEM DE HEMOGLOBINA GLICOSILADA", "glicemia-jejum"),
    ("DOSAGEM DE COLESTEROL TOTAL", "colesterol-triglicerides"),
    ("DOSAGEM DE TRIGLICERIDEOS", "colesterol-triglicerides"),
    ("HEMOGRAMA COMPLETO", "exames-de-sangue"),
    ("DOSAGEM DE TSH", "exames-de-sangue"),
    ("exame de sangue", "exames-de-sangue"),
    ("ANALISE DE CARACTERES FISICOS, ELEMENTOS E SEDIMENTO DA URINA", "exame-urina"),
    ("urina tipo 1", "exame-urina"),
    ("UROCULTURA", "exame-urina"),
    ("PESQUISA DE OVOS E CISTOS DE PARASITAS (PARASITOLOGICO DE FEZES)", "exame-fezes"),
    ("CONSULTA EM ENDOCRINOLOGIA", "consulta-especialista"),
    ("consulta cardiologista", "consulta-especialista"),
    ("CONSULTA MEDICA EM ATENCAO ESPECIALIZADA - ORTOPEDIA", "consulta-especialista"),
    ("como desmarcar minha consulta", "confirmar-liberar-vaga"),
    # Fora da base: o certo é devolver nada
    ("RESSONANCIA MAGNETICA DE JOELHO", None),
    ("TOMOGRAFIA COMPUTADORIZADA DE CRANIO", None),
    ("DENSITOMETRIA OSSEA", None),
    ("ELETROENCEFALOGRAMA", None),
    ("ESPIROMETRIA", None),
    ("sessao de fisioterapia", None),
    ("vacina da gripe", None),
]

# TESTE: escrito à parte e NÃO usado para ajustar nada. É o número honesto.
CASOS_TESTE = [
    ("US ABDOMINAL", "ultrassom-abdome"),
    ("ecografia abdominal", "ultrassom-abdome"),
    ("ultrassom da bexiga", "ultrassom-pelvico-rins"),
    ("EDA com biopsia", "endoscopia"),
    ("exame do estomago", "endoscopia"),
    ("colonoscopia com biopsia", "colonoscopia"),
    ("eletro do coração", "eletrocardiograma"),
    ("ergometria", "teste-ergometrico"),
    ("ecodoppler cardiaco", "ecocardiograma"),
    ("mamografia diagnostica", "mamografia"),
    ("rx de torax", "raio-x"),
    ("radiografia de coluna lombo-sacra", "raio-x"),
    ("glicose em jejum", "glicemia-jejum"),
    ("curva glicemica", "glicemia-jejum"),
    ("lipidograma", "colesterol-triglicerides"),
    ("HDL colesterol", "colesterol-triglicerides"),
    ("dosagem de creatinina", "exames-de-sangue"),
    ("hemograma", "exames-de-sangue"),
    ("EAS", "exame-urina"),
    ("parasitologico", "exame-fezes"),
    ("sangue oculto nas fezes", "exame-fezes"),
    ("consulta em neurologia", "consulta-especialista"),
    ("primeira consulta dermatologia", "consulta-especialista"),
    ("quero liberar minha vaga", "confirmar-liberar-vaga"),
    ("ULTRASSONOGRAFIA TRANSVAGINAL", None),
    ("ultrassom com doppler de membros inferiores", None),
    ("ressonancia de coluna", None),
    ("tomografia de abdome", None),
    ("holter 24 horas", None),
    ("audiometria", None),
    ("cintilografia", None),
    ("biopsia de prostata", None),
    ("papanicolau", None),
    ("teste do pezinho", None),
]


def avaliar(base: BaseConhecimento, limiar: float, casos: list) -> dict:
    acertos1 = acertos3 = rr = 0.0
    n_pos = n_neg = neg_ok = 0
    detalhes = []
    for consulta, esperado in casos:
        scores = base.pontuar(consulta)
        ordem = np.argsort(-scores)
        ids = [base.docs[i].id for i in ordem if scores[i] >= limiar]
        topo = (base.docs[ordem[0]].id, round(float(scores[ordem[0]]), 3))
        if esperado is None:
            n_neg += 1
            ok = len(ids) == 0
            neg_ok += ok
        else:
            n_pos += 1
            ok = bool(ids) and ids[0] == esperado
            acertos1 += ok
            acertos3 += esperado in ids[:3]
            rr += 1 / (ids.index(esperado) + 1) if esperado in ids else 0
        detalhes.append({"consulta": consulta, "esperado": esperado, "devolvido": ids[0] if ids else None,
                         "melhor_score": topo, "ok": bool(ok)})
    return {
        "limiar": limiar,
        "acerto@1": round(acertos1 / n_pos, 3),
        "acerto@3": round(acertos3 / n_pos, 3),
        "mrr": round(rr / n_pos, 3),
        "nao_encontrado_correto": round(neg_ok / n_neg, 3),
        "n_positivos": n_pos,
        "n_fora_da_base": n_neg,
        "detalhes": detalhes,
    }


def tabela_metricas(r: dict) -> list[str]:
    return [
        "| Métrica | Valor |",
        "|---|---|",
        f"| Acerto@1 (documento certo em 1º) | {r['acerto@1']:.1%} |",
        f"| Acerto@3 | {r['acerto@3']:.1%} |",
        f"| MRR | {r['mrr']} |",
        f"| Fora da base corretamente sem resposta | {r['nao_encontrado_correto']:.1%} |",
        f"| Buscas | {r['n_positivos']} na base + {r['n_fora_da_base']} fora |",
    ]


def tabela_casos(r: dict) -> list[str]:
    return [
        "| Busca | Esperado | Devolvido | Melhor candidato (score) | OK |",
        "|---|---|---|---|---|",
        *[f"| {d['consulta']} | {d['esperado'] or '(nada)'} | {d['devolvido'] or '(nada)'} | "
          f"{d['melhor_score'][0]} ({d['melhor_score'][1]}) | {'sim' if d['ok'] else '**não**'} |"
          for d in r["detalhes"]],
    ]


def main() -> None:
    base = BaseConhecimento()
    varredura = [avaliar(base, lim, CASOS_CALIBRACAO) for lim in np.round(np.arange(0.10, 0.41, 0.02), 2)]
    calib = avaliar(base, SCORE_MINIMO, CASOS_CALIBRACAO)
    teste = avaliar(base, SCORE_MINIMO, CASOS_TESTE)

    linhas = [
        "# Avaliação do RAG (recuperação de orientações de preparo)",
        "",
        f"Gerado por `scripts/avaliar_rag.py`. Base com {len(base.docs)} documentos. Limiar mínimo de score em uso: "
        f"**{SCORE_MINIMO}**.",
        "",
        "Dois conjuntos de buscas rotuladas, com nomes como chegam da regulação (maiúsculas, abreviações, "
        "erros de digitação) e exames que **não** estão na base:",
        "",
        "- **calibração**: usado para escolher o limiar e ajustar os termos dos documentos;",
        "- **teste**: escrito à parte e nunca usado para ajuste. É o resultado que vale.",
        "",
        "## Resultado no conjunto de teste",
        "",
        *tabela_metricas(teste),
        "",
        "## Resultado no conjunto de calibração",
        "",
        *tabela_metricas(calib),
        "",
        "## Escolha do limiar (conjunto de calibração)",
        "",
        "Limiar baixo acerta mais exames, mas manda preparo de outro exame quando o procedimento não está na base. "
        "Limiar alto recusa demais. Mandar preparo errado é pior do que não mandar (a mensagem então só diz para "
        "seguir o pedido médico), por isso o limiar fica no meio da faixa em que nenhuma busca fora da base recebe "
        "resposta e o acerto@1 não cai.",
        "",
        "| Limiar | Acerto@1 | Fora da base sem resposta |",
        "|---|---|---|",
        *[f"| {v['limiar']:.2f} | {v['acerto@1']:.1%} | {v['nao_encontrado_correto']:.1%} |" for v in varredura],
        "",
        "## Caso a caso: teste",
        "",
        *tabela_casos(teste),
        "",
        "## Caso a caso: calibração",
        "",
        *tabela_casos(calib),
    ]
    config.DIR_EVIDENCIAS.mkdir(exist_ok=True)
    (config.DIR_EVIDENCIAS / "rag_avaliacao.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (config.DIR_EVIDENCIAS / "rag_avaliacao.json").write_text(
        json.dumps({"limiar": SCORE_MINIMO, "teste": teste, "calibracao": calib,
                    "varredura_calibracao": [{k: v for k, v in x.items() if k != "detalhes"} for x in varredura]},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    for nome, r in (("TESTE", teste), ("calibração", calib)):
        print(f"{nome}: acerto@1 {r['acerto@1']:.1%} | acerto@3 {r['acerto@3']:.1%} | MRR {r['mrr']} | "
              f"fora da base sem resposta {r['nao_encontrado_correto']:.1%}")
        for d in r["detalhes"]:
            if not d["ok"]:
                print("   erro:", d["consulta"], "->", d["devolvido"], d["melhor_score"])


if __name__ == "__main__":
    main()
