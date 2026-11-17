"""Servidor que imita a API do Gemini (generateContent) para testar o workflow do n8n sem chave e sem custo.

Uso: python tests/gemini_falso.py [porta]   (padrão 8790)
Depois suba o n8n com GEMINI_BASE_URL=http://localhost:8790 (scripts/n8n_iniciar.ps1 -GeminiFalso).

Respostas especiais, conforme o texto do procedimento no prompt:
- contém "FALHA500"  -> HTTP 500
- contém "BLOQUEIO"  -> resposta bloqueada (finishReason SAFETY)
- contém "JSONRUIM"  -> texto que não é JSON
Nos demais casos devolve uma mensagem válida montada a partir do prompt.
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def montar(prompt: str) -> dict:
    campo = lambda nome: (re.search(rf"^{nome}: (.*)$", prompt, re.M) or [None, ""])[1]  # noqa: E731
    data = re.search(r"\d{2}/\d{2}", campo("data"))
    data = data.group(0) if data else ""
    hora, unidade, proc = campo("hora"), campo("unidade"), campo("procedimento")
    bloco = prompt.split("<orientacoes>")[1].split("</orientacoes>")[0].strip()
    itens = [l for l in bloco.splitlines() if l.startswith("Preparo: ")][:2]
    preparo = " ".join(i.split(": ", 1)[1] for i in itens)
    return {
        "orientacao_corresponde": bool(itens),
        "sms": f"Olá, {{nome}}! {proc} em {data} às {hora}, {unidade}. Responda SIM para confirmar ou NAO para liberar a vaga.",
        "app": f"Olá, {{nome}}!\n- Quando: {data}, {hora}\n- Onde: {unidade}\n" + (f"- {preparo}\n" if preparo else "")
               + "Responda SIM para confirmar ou NAO para liberar a vaga para outra pessoa da fila.",
        "itens_usados": itens,
    }


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        corpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        prompt = corpo["contents"][0]["parts"][0]["text"]
        status, resposta = 200, None
        if not self.headers.get("x-goog-api-key"):
            status, resposta = 400, {"error": {"code": 400, "message": "API key not valid."}}
        elif "FALHA500" in prompt:
            status, resposta = 500, {"error": {"code": 500, "message": "Internal error"}}
        elif "BLOQUEIO" in prompt:
            resposta = {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]}
        elif "JSONRUIM" in prompt:
            resposta = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "isto não é json"}]}}]}
        else:
            texto = json.dumps(montar(prompt), ensure_ascii=False)
            resposta = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": texto}]}}],
                        "modelVersion": "gemini-falso-teste", "usageMetadata": {"totalTokenCount": 0}}
        dados = json.dumps(resposta, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8790
    print(f"Gemini falso em http://localhost:{porta}")
    HTTPServer(("127.0.0.1", porta), Handler).serve_forever()
