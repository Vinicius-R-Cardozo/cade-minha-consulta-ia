# Avaliação do modelo de previsão de falta

Gerado por `scripts/treinar.py` em 2026-11-16. Base: **sintetica**.

> **Base sintética.** Estes números só mostram que o pipeline funciona. Para o resultado real, coloque o CSV do Kaggle em `data/raw/` e rode de novo.

## Divisão temporal

Treino no passado, validação e teste no futuro, como seria em produção.

| Conjunto | Período | Consultas |
|---|---|---|
| treino | 2016-04-28 a 2016-05-24 | 18988 |
| validacao | 2016-05-25 a 2016-05-31 | 5225 |
| teste | 2016-06-01 a 2016-06-08 | 5787 |

## Comparação no conjunto de teste

Limiar escolhido na validação para sinalizar as 30% consultas de maior risco (capacidade de reforço da equipe).

| Modelo | ROC-AUC | PR-AUC | Recall | Precisão | F1 | Brier |
|---|---|---|---|---|---|---|
| Baseline (taxa média) | 0.5 | 0.2081 | 1.0 | 0.2081 | 0.3444 | 0.1648 |
| Regressão logística | 0.7228 | 0.3622 | 0.5174 | 0.3637 | 0.4272 | 0.2123 |
| Gradient boosting | 0.7334 | 0.3804 | 0.5507 | 0.3786 | 0.4487 | 0.2086 |

Modelo escolhido (maior PR-AUC na validação): **Gradient boosting**.

### Como ler

- Taxa real de falta no teste: 20.8%.
- Contatando 30% das consultas (as de maior risco), o modelo cobre **55% das faltas**. Sem modelo, contatar 30% ao acaso cobriria cerca de 30%.
- Entre as consultas sinalizadas, 38% de fato faltaram (contra 21% na média).
- Matriz de confusão: VP 663, FP 1088, FN 541, VN 3495.
- Priorizamos **recall** e **PR-AUC** porque a classe de interesse (falta) é minoritária e deixar de avisar quem vai faltar custa mais do que um lembrete a mais.

![curvas](modelo_curvas.png)

## Importância dos atributos

| Atributo | Queda no PR-AUC |
|---|---|
| dias_antecedencia | 0.1597 ± 0.0026 |
| idade | 0.0194 ± 0.0051 |
| taxa_faltas_anteriores | 0.0093 ± 0.0011 |
| sms_recebido | 0.0061 ± 0.0029 |
| bolsa_familia | 0.0043 ± 0.0016 |
| dia_semana | 0.0028 ± 0.0016 |
| faltas_anteriores | 0.0025 ± 0.0015 |
| diabetes | 0.0016 ± 0.0005 |
| genero_f | 0.0015 ± 0.0013 |
| consultas_anteriores | 0.0015 ± 0.001 |
| alcoolismo | 0.0008 ± 0.0037 |
| deficiencia | 0.0001 ± 0.0001 |
| mesmo_dia | 0.0 ± 0.0 |
| hipertensao | -0.0003 ± 0.0007 |

![importancia](modelo_importancia.png)

## Comportamento por grupo (uso responsável)

O modelo só decide **a intensidade do lembrete**, nunca o acesso à consulta. Mesmo assim, conferimos se algum grupo é sinalizado de forma muito diferente da sua taxa real de falta.

| Grupo | Consultas | Taxa real de falta | Fração sinalizada | Recall |
|---|---|---|---|---|
| genero: F | 3783 | 20.8% | 30.8% | 0.5609 |
| genero: M | 2004 | 20.8% | 29.3% | 0.5312 |
| faixa_etaria: 0-11 | 792 | 18.9% | 32.8% | 0.6 |
| faixa_etaria: 12-17 | 645 | 25.7% | 42.2% | 0.6747 |
| faixa_etaria: 18-29 | 1265 | 22.9% | 41.9% | 0.669 |
| faixa_etaria: 30-59 | 2084 | 20.8% | 25.1% | 0.4688 |
| faixa_etaria: 60+ | 1001 | 16.5% | 16.6% | 0.3879 |
