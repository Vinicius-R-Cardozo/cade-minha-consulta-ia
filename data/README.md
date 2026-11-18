# Dados

## Base usada no modelo: Medical Appointment No Shows

O arquivo **[KaggleV2-May-2016.csv](KaggleV2-May-2016.csv)**, nesta pasta, é a base com que o modelo de risco de falta
foi treinado e avaliado. Não é preciso baixar nada: `python scripts/treinar.py` lê o arquivo daqui.

| Item | Valor |
|---|---|
| Origem | [Medical Appointment No Shows](https://www.kaggle.com/datasets/joniarroba/noshowappointments), publicada no Kaggle por Joni Hoppen (Aquarela Analytics) |
| Conteúdo | 110.527 consultas da rede pública de Vitória (ES), de 29/04 a 08/06/2016, com a marcação de comparecimento (`No-show`) |
| Colunas | 14: `PatientId`, `AppointmentID`, `Gender`, `ScheduledDay`, `AppointmentDay`, `Age`, `Neighbourhood`, `Scholarship`, `Hipertension`, `Diabetes`, `Alcoholism`, `Handcap`, `SMS_received`, `No-show` |
| Taxa de falta | 20,19% |
| Tamanho | 10,7 MB |
| SHA-256 | `9132d3e7d0246617df9041d3764f20ad6f08e7b0d9f0997fa254fc5e52eda27d` |

Os dados já vêm anonimizados: `PatientId` e `AppointmentID` são códigos, sem nome, CPF ou endereço. O uso aqui é
acadêmico, sem fins comerciais, com crédito aos autores. Antes de qualquer outro uso, confira os termos na página
do Kaggle.

### De onde veio esta cópia

O download direto do Kaggle exige login. Usamos a cópia pública do mesmo arquivo publicada no repositório
`mriffaud/Medical-Appointment-No-Shows` do GitHub. Antes de usar, conferimos:

- o SHA-256 acima, idêntico ao de uma segunda cópia independente (`chasekregor/NoShows`);
- as 110.527 linhas e as 14 colunas originais;
- a taxa de falta de 20,19%, o período de 29/04 a 08/06/2016 e os mesmos defeitos conhecidos da base (por exemplo, idade −1).

Para conferir: `sha256sum data/KaggleV2-May-2016.csv`.

### Tratamento (`src/cademinhaconsulta/dados.py`)

| Problema na base | Tratamento |
|---|---|
| Colunas com grafia errada (`Hipertension`, `Handcap`) | Renomeadas |
| Idade negativa ou acima de 110 | Linha descartada (11 linhas no total, com o item abaixo) |
| Agendamento depois da data da consulta | Linha descartada |
| `AppointmentDay` sem hora | Antecedência calculada em dias |
| `Handcap` de 0 a 4 | Virou sim/não (`deficiencia`) |
| Histórico do paciente | Calculado só com dias anteriores, para não vazar o resultado |

Depois da limpeza ficam 110.516 consultas. O campo `Neighbourhood` (bairro) não entra no modelo: ajuda pouco a prever
e aumenta o risco de reidentificação e de tratar bairros de forma desigual.

## Base sintética (só para testes)

Os testes automáticos (`python -m pytest`) geram, numa pasta temporária, consultas falsas no mesmo formato, com
`scripts/gerar_sintetico.py`. Assim os testes rodam em segundos e sem depender da base real. Os dados sintéticos não
entram no modelo versionado nem em nenhum resultado do README.
