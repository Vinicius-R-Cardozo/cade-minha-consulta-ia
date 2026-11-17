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

## Cópia usada neste projeto

O download do Kaggle exige login. Usamos uma cópia pública do mesmo arquivo, publicada no repositório
`mriffaud/Medical-Appointment-No-Shows` no GitHub (`data/KaggleV2-May-2016.csv`). Antes de usar, conferimos:

- SHA-256 `9132d3e7d0246617df9041d3764f20ad6f08e7b0d9f0997fa254fc5e52eda27d`, idêntico ao de uma segunda cópia independente (`chasekregor/NoShows`);
- 110.527 linhas e as 14 colunas originais;
- 20,19% de faltas, consultas de 29/04 a 08/06/2016 e os mesmos defeitos conhecidos da base (idade −1, por exemplo).

Para conferir a sua cópia: `sha256sum data/raw/KaggleV2-May-2016.csv`.
