"""RAG básico: recupera a orientação de preparo certa para a consulta ou exame agendado.

Por que TF-IDF e não embeddings de uma API?
- a base é pequena (um documento por exame) e as buscas são nomes de exame, com variações e erros de digitação;
- n-gramas de caracteres pegam "ultrasom", "ultra-som" e "USG abdome" sem depender de serviço externo;
- roda offline, em milissegundos, sem custo e sem enviar nada para fora (útil em locais com pouca conexão).
A troca por embeddings fica fácil: basta outra implementação de `BaseConhecimento.buscar`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import config

# Abaixo deste score a busca devolve "nada encontrado" em vez de chutar um documento errado.
# Valor calibrado em scripts/avaliar_rag.py (ver evidencias/rag_avaliacao.md).
SCORE_MINIMO = 0.30
# Acima disto a recuperação é "confiança alta" e o template (sem IA) pode usar o preparo direto.
# Entre SCORE_MINIMO e CONFIANCA_ALTA, só a IA generativa usa o documento, e só depois de verificar
# que ele é do mesmo procedimento (ver geracao.py). Ver evidencias/rag_avaliacao.md.
CONFIANCA_ALTA = 0.50
PESO_TITULO = 0.65
PESO_SIMILARIDADE = 0.5   # metade similaridade de caracteres, metade cobertura de palavras
SIM_PALAVRA = 0.84        # duas palavras "batem" se forem pelo menos 84% parecidas (pega erro de digitação)

# Palavras genéricas dos nomes de procedimento da tabela do SUS: não ajudam a distinguir um exame do outro.
PALAVRAS_VAZIAS = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "com", "por", "via", "ou", "a", "o", "no", "na",
    "dosagem", "pesquisa", "determinacao", "analise", "exame", "exames", "medica", "medico", "atencao",
    "minha", "meu", "como", "pa", "perfil", "bilateral", "unilateral", "total", "simples",
}


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def palavras(texto_normalizado: str) -> list[str]:
    return [p for p in texto_normalizado.split() if len(p) >= 2 and p not in PALAVRAS_VAZIAS]


def _parecidas(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if len(a) >= 5 and b.startswith(a):  # abreviação: "colono" -> "colonoscopia"
        return 0.95
    return SequenceMatcher(None, a, b).ratio()


def cobertura_palavras(consulta_normalizada: str, vocabulario: set[str]) -> float:
    """Fração das palavras informativas da busca que aparecem (exatas ou quase) no cabeçalho do documento.

    É o que impede "eletroencefalograma" de casar com "eletrocardiograma": os n-gramas de caracteres são
    parecidos, mas nenhuma palavra bate de verdade.
    """
    termos = palavras(consulta_normalizada)
    if not termos:
        return 0.0
    total = 0.0
    for t in termos:
        melhor = max((_parecidas(t, v) for v in vocabulario), default=0.0)
        total += melhor if melhor >= SIM_PALAVRA else 0.0
    return total / len(termos)


@dataclass
class Documento:
    id: str
    titulo: str
    termos: str
    categoria: str
    secoes: dict[str, list[str]]
    texto: str

    @property
    def fonte(self) -> str:
        return f"base_conhecimento/{self.id}.md"


@dataclass
class Resultado:
    documento: Documento
    score: float

    @property
    def confianca_alta(self) -> bool:
        return self.score >= CONFIANCA_ALTA


def ler_documento(caminho: Path) -> Documento:
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    titulo = linhas[0].lstrip("# ").strip()
    termos = categoria = ""
    secoes: dict[str, list[str]] = {}
    atual = None
    for linha in linhas[1:]:
        if linha.startswith("Termos:"):
            termos = linha.split(":", 1)[1].strip()
        elif linha.startswith("Categoria:"):
            categoria = linha.split(":", 1)[1].strip()
        elif linha.startswith("## "):
            atual = linha[3:].strip()
            secoes[atual] = []
        elif atual and linha.strip().startswith("- "):
            secoes[atual].append(linha.strip()[2:])
    return Documento(caminho.stem, titulo, termos, categoria, secoes, "\n".join(linhas))


class BaseConhecimento:
    def __init__(self, pasta: Path = config.DIR_BASE_CONHECIMENTO):
        self.docs = [ler_documento(p) for p in sorted(pasta.glob("*.md")) if p.name.lower() != "readme.md"]
        if not self.docs:
            raise FileNotFoundError(f"Nenhum documento em {pasta}")
        cabecalhos = [normalizar(f"{d.titulo} {d.termos}") for d in self.docs]
        corpos = [normalizar(d.texto) for d in self.docs]
        self._vt = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self._mt = self._vt.fit_transform(cabecalhos)
        self._vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self._mc = self._vc.fit_transform(corpos)
        self._vocab = [set(palavras(c)) for c in cabecalhos]

    def pontuar(self, consulta: str) -> np.ndarray:
        q = normalizar(consulta)
        if not q:
            return np.zeros(len(self.docs))
        st = cosine_similarity(self._vt.transform([q]), self._mt)[0]
        sc = cosine_similarity(self._vc.transform([q]), self._mc)[0]
        similaridade = PESO_TITULO * st + (1 - PESO_TITULO) * sc
        cobertura = np.array([cobertura_palavras(q, voc) for voc in self._vocab])
        return PESO_SIMILARIDADE * similaridade + (1 - PESO_SIMILARIDADE) * cobertura

    def buscar(self, consulta: str, k: int = 2, score_minimo: float = SCORE_MINIMO) -> list[Resultado]:
        scores = self.pontuar(consulta)
        ordem = np.argsort(-scores)[:k]
        return [Resultado(self.docs[i], float(scores[i])) for i in ordem if scores[i] >= score_minimo]

    def por_id(self, doc_id: str) -> Documento | None:
        return next((d for d in self.docs if d.id == doc_id), None)
