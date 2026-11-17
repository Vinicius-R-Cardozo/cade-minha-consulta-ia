# Dados

## Base real: Medical Appointment No Shows (Kaggle)

- Página: https://www.kaggle.com/datasets/joniarroba/noshowappointments
- Conteúdo: cerca de 110 mil consultas da rede pública de Vitória (ES), abril a junho de 2016, com a marcação
  de comparecimento ("No-show").
- Dados anonimizados na origem: `PatientId` e `AppointmentID` são códigos, sem nome, CPF ou endereço.
- Como usar: baixe `KaggleV2-May-2016.csv` (precisa de conta no Kaggle) e coloque em `data/raw/`.
  O arquivo não vai para o Git. Confira a licença na página antes de redistribuir.

Problemas conhecidos tratados em `src/vagacerta/dados.py`:

| Problema | Tratamento |
|---|---|
| Colunas com grafia errada (`Hipertension`, `Handcap`) | Renomeadas |
| Idade negativa | Linha descartada |
| Agendamento depois da data da consulta | Linha descartada |
| `AppointmentDay` sem hora | Antecedência calculada em dias |
| `Handcap` de 0 a 4 | Virou sim/não (`deficiencia`) |
| Histórico do paciente | Calculado só com dias anteriores, para não vazar o resultado |

O campo `Neighbourhood` (bairro) não entra no modelo: ajuda pouco a prever e aumenta o risco de reidentificação
e de tratar bairros de forma desigual.

## Base sintética

`python scripts/gerar_sintetico.py` gera `data/sintetico/consultas_sinteticas.csv` no mesmo formato.
Nenhum dado é real. Serve para os testes automáticos e para rodar o projeto sem a base do Kaggle.
