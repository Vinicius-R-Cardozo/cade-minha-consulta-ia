"""Gera uma base SINTÉTICA no mesmo formato do CSV do Kaggle (KaggleV2-May-2016.csv).

Serve para: rodar os testes automatizados, demonstrar o pipeline sem a base real e nunca expor dado de paciente.
As relações (antecedência, idade, histórico de faltas, SMS) imitam as tendências descritas na literatura
sobre a base de Vitória, mas os números NÃO são reais. Métricas obtidas aqui não valem como resultado.

Uso: python scripts/gerar_sintetico.py [--n 30000] [--seed 7] [--saida caminho.csv]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from cademinhaconsulta import config  # noqa: E402


def gerar(n: int = 30000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_pacientes = int(n * 0.6)
    pac_id = rng.integers(10**10, 10**11, n_pacientes).astype(float)
    pac_idade = np.clip(rng.gamma(2.0, 19, n_pacientes), 0, 105).astype(int)
    pac_genero = rng.choice(["F", "M"], n_pacientes, p=[0.65, 0.35])
    pac_propensao = rng.normal(0, 0.8, n_pacientes)  # "jeito" de cada paciente: gera histórico consistente
    pac_bolsa = rng.random(n_pacientes) < 0.10
    pac_hiper = rng.random(n_pacientes) < np.clip(pac_idade / 150, 0.02, 0.6)
    pac_diab = rng.random(n_pacientes) < np.clip(pac_idade / 400, 0.01, 0.25)
    pac_alcool = rng.random(n_pacientes) < 0.03
    pac_def = rng.random(n_pacientes) < 0.02

    idx = rng.choice(n_pacientes, n, p=None)
    dia_consulta = pd.Timestamp("2016-04-29") + pd.to_timedelta(rng.integers(0, 41, n), unit="D")
    dia_consulta = dia_consulta.where(dia_consulta.day_of_week < 5, dia_consulta - pd.to_timedelta(2, unit="D"))
    mesmo_dia = rng.random(n) < 0.35
    antecedencia = np.where(mesmo_dia, 0, np.clip(rng.exponential(14, n), 1, 120)).astype(int)
    agendamento = dia_consulta - pd.to_timedelta(antecedencia, unit="D") + pd.to_timedelta(
        rng.integers(7 * 3600, 17 * 3600, n), unit="s")
    sms = (antecedencia >= 3) & (rng.random(n) < 0.55)

    idade = pac_idade[idx]
    logit = (
        -2.3
        + 0.55 * np.log1p(antecedencia)
        - 0.9 * mesmo_dia
        + 0.45 * ((idade >= 12) & (idade <= 30))
        - 0.35 * (idade >= 60)
        + 0.25 * pac_bolsa[idx]
        + 0.40 * pac_alcool[idx]
        - 0.25 * sms
        + 0.9 * pac_propensao[idx]
    )
    faltou = rng.random(n) < 1 / (1 + np.exp(-logit))

    bairros = [f"BAIRRO {i:02d}" for i in range(1, 41)]
    return pd.DataFrame({
        "PatientId": pac_id[idx],
        "AppointmentID": np.arange(5_000_000, 5_000_000 + n),
        "Gender": pac_genero[idx],
        "ScheduledDay": agendamento.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "AppointmentDay": dia_consulta.strftime("%Y-%m-%dT00:00:00Z"),
        "Age": idade,
        "Neighbourhood": rng.choice(bairros, n),
        "Scholarship": pac_bolsa[idx].astype(int),
        "Hipertension": pac_hiper[idx].astype(int),
        "Diabetes": pac_diab[idx].astype(int),
        "Alcoholism": pac_alcool[idx].astype(int),
        "Handcap": pac_def[idx].astype(int),
        "SMS_received": sms.astype(int),
        "No-show": np.where(faltou, "Yes", "No"),
    })


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=30000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--saida", type=Path, default=config.CSV_SINTETICO)
    a = p.parse_args()
    df = gerar(a.n, a.seed)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.saida, index=False)
    print(f"{len(df)} consultas sintéticas -> {a.saida} (taxa de falta {(df['No-show'] == 'Yes').mean():.1%})")


if __name__ == "__main__":
    main()
