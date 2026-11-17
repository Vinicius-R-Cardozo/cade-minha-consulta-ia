# Workflow n8n — IA generativa do Vaga Certa

O arquivo [vagacerta-mensagem.json](vagacerta-mensagem.json) é o workflow que gera a mensagem de confirmação
com o **Google Gemini**. O serviço Python chama este workflow por webhook.

```
Webhook (POST /webhook/vagacerta-mensagem)
   └─ IF: token X-Vagacerta-Token confere?
        ├─ sim → HTTP Request: Gemini generateContent (JSON com schema)
        │          └─ Code: trata erro HTTP, bloqueio, JSON inválido
        │               └─ Respond: { ok, modelo, resultado } ou { ok: false, erro }
        └─ não → Respond 401
```

| Nó | O que faz |
|---|---|
| Recebe pedido do Vaga Certa | Webhook que recebe `{ sistema, prompt, schema }` do Python. |
| Token confere? | Compara o cabeçalho `X-Vagacerta-Token` com `VAGACERTA_N8N_TOKEN`. Só o serviço Vaga Certa chama o workflow. |
| Gemini gera a mensagem | Chama `generateContent` com instrução de sistema, prompt, `responseMimeType: application/json`, `responseSchema` e temperatura 0,3. A chave vai no cabeçalho `x-goog-api-key` e vem da variável de ambiente `GEMINI_API_KEY`. |
| Confere resposta do Gemini | Converte a resposta no contrato do Python e transforma erro HTTP, bloqueio de segurança (`finishReason` diferente de `STOP`) e JSON inválido em `{ ok: false, erro }`. |
| Devolve para o Vaga Certa | Responde ao webhook. |

Por que o prompt fica no Python e não no n8n: as regras do prompt, o schema e a validação da saída são testados
automaticamente (`pytest`). O n8n cuida da integração com o provedor de IA e da chave. Trocar o Gemini por outro
modelo é mexer só neste workflow.

## Como subir

Requisitos: Node 24 e `npm install -g n8n`.

1. Crie uma chave gratuita do Gemini em https://aistudio.google.com/apikey.
2. No `.env` da raiz do projeto, preencha `GEMINI_API_KEY` e `VAGACERTA_N8N_TOKEN` (o mesmo token é usado pelo Python).
3. Rode o script:

```bash
powershell -ExecutionPolicy Bypass -File scripts/n8n_iniciar.ps1
```

O script:
- lê o `.env`;
- guarda os dados do n8n em `n8n/.local/`, fora do Git;
- importa este workflow e o publica (ativa);
- sobe o n8n em http://localhost:5678.

No primeiro acesso ao editor, o n8n pede para criar um usuário local.

`N8N_BLOCK_ENV_ACCESS_IN_NODE=false` é ligado pelo script para o workflow ler a chave e o token das variáveis de
ambiente. Assim nenhuma credencial fica gravada no JSON do workflow nem no Git.

## Testar sem chave (Gemini falso)

Para testar o caminho completo Python → n8n → "Gemini" sem chave e sem custo, abra dois terminais.

No primeiro, suba o servidor que imita a API do Gemini:

```bash
python tests/gemini_falso.py
```

No segundo, suba o n8n apontando para ele:

```bash
powershell -ExecutionPolicy Bypass -File scripts/n8n_iniciar.ps1 -GeminiFalso
```

Depois rode `python scripts/avaliar_mensagens.py --modo ia`.
