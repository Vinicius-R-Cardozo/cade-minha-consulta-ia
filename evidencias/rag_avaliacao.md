# Avaliação do RAG (recuperação de orientações de preparo)

Gerado por `scripts/avaliar_rag.py`. Base com 16 documentos. Limiar mínimo de score em uso: **0.3**.

Dois conjuntos de buscas rotuladas, com nomes como chegam da regulação (maiúsculas, abreviações, erros de digitação) e exames que **não** estão na base:

- **calibração**: usado para escolher o limiar e ajustar os termos dos documentos;
- **teste**: escrito à parte e nunca usado para ajuste. É o resultado que vale.

## Resultado no conjunto de teste

| Métrica | Valor |
|---|---|
| Acerto@1 (documento certo em 1º) | 100.0% |
| Acerto@3 | 100.0% |
| MRR | 1.0 |
| Fora da base corretamente sem resposta | 60.0% |
| Buscas | 24 na base + 10 fora |

## Resultado no conjunto de calibração

| Métrica | Valor |
|---|---|
| Acerto@1 (documento certo em 1º) | 100.0% |
| Acerto@3 | 100.0% |
| MRR | 1.0 |
| Fora da base corretamente sem resposta | 100.0% |
| Buscas | 35 na base + 7 fora |

## Escolha do limiar (conjunto de calibração)

Limiar baixo acerta mais exames, mas manda preparo de outro exame quando o procedimento não está na base. Limiar alto recusa demais. Mandar preparo errado é pior do que não mandar (a mensagem então só diz para seguir o pedido médico), por isso o limiar fica no meio da faixa em que nenhuma busca fora da base recebe resposta e o acerto@1 não cai.

| Limiar | Acerto@1 | Fora da base sem resposta |
|---|---|---|
| 0.10 | 100.0% | 42.9% |
| 0.12 | 100.0% | 42.9% |
| 0.14 | 100.0% | 57.1% |
| 0.16 | 100.0% | 71.4% |
| 0.18 | 100.0% | 85.7% |
| 0.20 | 100.0% | 85.7% |
| 0.22 | 100.0% | 100.0% |
| 0.24 | 100.0% | 100.0% |
| 0.26 | 100.0% | 100.0% |
| 0.28 | 100.0% | 100.0% |
| 0.30 | 100.0% | 100.0% |
| 0.32 | 100.0% | 100.0% |
| 0.34 | 100.0% | 100.0% |
| 0.36 | 100.0% | 100.0% |
| 0.38 | 100.0% | 100.0% |
| 0.40 | 100.0% | 100.0% |

## Caso a caso: teste

| Busca | Esperado | Devolvido | Melhor candidato (score) | OK |
|---|---|---|---|---|
| US ABDOMINAL | ultrassom-abdome | ultrassom-abdome | ultrassom-abdome (0.459) | sim |
| ecografia abdominal | ultrassom-abdome | ultrassom-abdome | ultrassom-abdome (0.729) | sim |
| ultrassom da bexiga | ultrassom-pelvico-rins | ultrassom-pelvico-rins | ultrassom-pelvico-rins (0.721) | sim |
| EDA com biopsia | endoscopia | endoscopia | endoscopia (0.307) | sim |
| exame do estomago | endoscopia | endoscopia | endoscopia (0.641) | sim |
| colonoscopia com biopsia | colonoscopia | colonoscopia | colonoscopia (0.474) | sim |
| eletro do coração | eletrocardiograma | eletrocardiograma | eletrocardiograma (0.755) | sim |
| ergometria | teste-ergometrico | teste-ergometrico | teste-ergometrico (0.773) | sim |
| ecodoppler cardiaco | ecocardiograma | ecocardiograma | ecocardiograma (0.734) | sim |
| mamografia diagnostica | mamografia | mamografia | mamografia (0.502) | sim |
| rx de torax | raio-x | raio-x | raio-x (0.305) | sim |
| radiografia de coluna lombo-sacra | raio-x | raio-x | raio-x (0.419) | sim |
| glicose em jejum | glicemia-jejum | glicemia-jejum | glicemia-jejum (0.758) | sim |
| curva glicemica | glicemia-jejum | glicemia-jejum | glicemia-jejum (0.779) | sim |
| lipidograma | colesterol-triglicerides | colesterol-triglicerides | colesterol-triglicerides (0.656) | sim |
| HDL colesterol | colesterol-triglicerides | colesterol-triglicerides | colesterol-triglicerides (0.693) | sim |
| dosagem de creatinina | exames-de-sangue | exames-de-sangue | exames-de-sangue (0.621) | sim |
| hemograma | exames-de-sangue | exames-de-sangue | exames-de-sangue (0.692) | sim |
| EAS | exame-urina | exame-urina | exame-urina (0.555) | sim |
| parasitologico | exame-fezes | exame-fezes | exame-fezes (0.798) | sim |
| sangue oculto nas fezes | exame-fezes | exame-fezes | exame-fezes (0.582) | sim |
| consulta em neurologia | consulta-especialista | consulta-especialista | consulta-especialista (0.671) | sim |
| primeira consulta dermatologia | consulta-especialista | consulta-especialista | consulta-especialista (0.5) | sim |
| quero liberar minha vaga | confirmar-liberar-vaga | confirmar-liberar-vaga | confirmar-liberar-vaga (0.526) | sim |
| ULTRASSONOGRAFIA TRANSVAGINAL | (nada) | ultrassom-abdome | ultrassom-abdome (0.452) | **não** |
| ultrassom com doppler de membros inferiores | (nada) | (nada) | ultrassom-abdome (0.298) | sim |
| ressonancia de coluna | (nada) | (nada) | glicemia-jejum (0.057) | sim |
| tomografia de abdome | (nada) | ultrassom-abdome | ultrassom-abdome (0.466) | **não** |
| holter 24 horas | (nada) | (nada) | ultrassom-pelvico-rins (0.03) | sim |
| audiometria | (nada) | (nada) | teste-ergometrico (0.173) | sim |
| cintilografia | (nada) | (nada) | raio-x (0.145) | sim |
| biopsia de prostata | (nada) | ultrassom-pelvico-rins | ultrassom-pelvico-rins (0.401) | **não** |
| papanicolau | (nada) | (nada) | exame-fezes (0.032) | sim |
| teste do pezinho | (nada) | teste-ergometrico | teste-ergometrico (0.404) | **não** |

## Caso a caso: calibração

| Busca | Esperado | Devolvido | Melhor candidato (score) | OK |
|---|---|---|---|---|
| ULTRASSONOGRAFIA DE ABDOMEN TOTAL | ultrassom-abdome | ultrassom-abdome | ultrassom-abdome (0.804) | sim |
| usg abdome superior | ultrassom-abdome | ultrassom-abdome | ultrassom-abdome (0.767) | sim |
| ultrasom do figado | ultrassom-abdome | ultrassom-abdome | ultrassom-abdome (0.666) | sim |
| ULTRASSONOGRAFIA PELVICA (GINECOLOGICA) | ultrassom-pelvico-rins | ultrassom-pelvico-rins | ultrassom-pelvico-rins (0.544) | sim |
| ultrassom de rins e vias urinarias | ultrassom-pelvico-rins | ultrassom-pelvico-rins | ultrassom-pelvico-rins (0.818) | sim |
| ULTRASSONOGRAFIA DE PROSTATA VIA ABDOMINAL | ultrassom-pelvico-rins | ultrassom-pelvico-rins | ultrassom-pelvico-rins (0.807) | sim |
| ENDOSCOPIA DIGESTIVA ALTA | endoscopia | endoscopia | endoscopia (0.876) | sim |
| endoscopia | endoscopia | endoscopia | endoscopia (0.783) | sim |
| COLONOSCOPIA (COLOSCOPIA) | colonoscopia | colonoscopia | colonoscopia (0.722) | sim |
| colono | colonoscopia | colonoscopia | colonoscopia (0.612) | sim |
| ELETROCARDIOGRAMA | eletrocardiograma | eletrocardiograma | eletrocardiograma (0.871) | sim |
| ECG | eletrocardiograma | eletrocardiograma | eletrocardiograma (0.638) | sim |
| TESTE DE ESFORCO / TESTE ERGOMETRICO | teste-ergometrico | teste-ergometrico | teste-ergometrico (0.908) | sim |
| ECOCARDIOGRAFIA TRANSTORACICA | ecocardiograma | ecocardiograma | ecocardiograma (0.55) | sim |
| ecocardiograma | ecocardiograma | ecocardiograma | ecocardiograma (0.831) | sim |
| MAMOGRAFIA BILATERAL PARA RASTREAMENTO | mamografia | mamografia | mamografia (0.8) | sim |
| mamografia | mamografia | mamografia | mamografia (0.807) | sim |
| RADIOGRAFIA DE TORAX (PA E PERFIL) | raio-x | raio-x | raio-x (0.477) | sim |
| raio x joelho | raio-x | raio-x | raio-x (0.482) | sim |
| DOSAGEM DE GLICOSE | glicemia-jejum | glicemia-jejum | glicemia-jejum (0.718) | sim |
| glicemia de jejum | glicemia-jejum | glicemia-jejum | glicemia-jejum (0.771) | sim |
| DOSAGEM DE HEMOGLOBINA GLICOSILADA | glicemia-jejum | glicemia-jejum | glicemia-jejum (0.467) | sim |
| DOSAGEM DE COLESTEROL TOTAL | colesterol-triglicerides | colesterol-triglicerides | colesterol-triglicerides (0.643) | sim |
| DOSAGEM DE TRIGLICERIDEOS | colesterol-triglicerides | colesterol-triglicerides | colesterol-triglicerides (0.768) | sim |
| HEMOGRAMA COMPLETO | exames-de-sangue | exames-de-sangue | exames-de-sangue (0.703) | sim |
| DOSAGEM DE TSH | exames-de-sangue | exames-de-sangue | exames-de-sangue (0.555) | sim |
| exame de sangue | exames-de-sangue | exames-de-sangue | exames-de-sangue (0.661) | sim |
| ANALISE DE CARACTERES FISICOS, ELEMENTOS E SEDIMENTO DA URINA | exame-urina | exame-urina | exame-urina (0.538) | sim |
| urina tipo 1 | exame-urina | exame-urina | exame-urina (0.724) | sim |
| UROCULTURA | exame-urina | exame-urina | exame-urina (0.707) | sim |
| PESQUISA DE OVOS E CISTOS DE PARASITAS (PARASITOLOGICO DE FEZES) | exame-fezes | exame-fezes | exame-fezes (0.509) | sim |
| CONSULTA EM ENDOCRINOLOGIA | consulta-especialista | consulta-especialista | consulta-especialista (0.677) | sim |
| consulta cardiologista | consulta-especialista | consulta-especialista | consulta-especialista (0.759) | sim |
| CONSULTA MEDICA EM ATENCAO ESPECIALIZADA - ORTOPEDIA | consulta-especialista | consulta-especialista | consulta-especialista (0.698) | sim |
| como desmarcar minha consulta | confirmar-liberar-vaga | confirmar-liberar-vaga | confirmar-liberar-vaga (0.731) | sim |
| RESSONANCIA MAGNETICA DE JOELHO | (nada) | (nada) | glicemia-jejum (0.063) | sim |
| TOMOGRAFIA COMPUTADORIZADA DE CRANIO | (nada) | (nada) | mamografia (0.126) | sim |
| DENSITOMETRIA OSSEA | (nada) | (nada) | teste-ergometrico (0.15) | sim |
| ELETROENCEFALOGRAMA | (nada) | (nada) | eletrocardiograma (0.22) | sim |
| ESPIROMETRIA | (nada) | (nada) | teste-ergometrico (0.169) | sim |
| sessao de fisioterapia | (nada) | (nada) | endoscopia (0.044) | sim |
| vacina da gripe | (nada) | (nada) | exame-urina (0.06) | sim |
