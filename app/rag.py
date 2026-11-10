"""RAG básico: recupera os trechos da base de conhecimento mais parecidos com o relato.

Escolha técnica: TF-IDF + similaridade de cosseno (scikit-learn).
A base é pequena (poucos documentos), então TF-IDF é suficiente, roda local,
sem custo e sem depender de outra API de embeddings.
"""
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import PASTA_BASE_CONHECIMENTO

STOPWORDS_PT = [
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "na",
    "no", "nas", "nos", "e", "ou", "que", "com", "por", "para", "pra", "se", "ao",
    "aos", "é", "foi", "tem", "ta", "está", "esta", "isso", "essa", "esse", "minha",
    "meu", "sua", "seu", "já", "ja", "mais", "muito", "não", "nao", "há", "ha",
]


@dataclass
class Trecho:
    fonte: str   # arquivo + título da seção
    texto: str


def carregar_trechos(pasta: Path = PASTA_BASE_CONHECIMENTO) -> list[Trecho]:
    """Divide cada .md da base em trechos, um por seção '## '."""
    trechos = []
    for arquivo in sorted(pasta.glob("*.md")):
        titulo_atual, linhas = None, []
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            if linha.startswith("## "):
                if titulo_atual:
                    trechos.append(Trecho(f"{arquivo.name} > {titulo_atual}", "\n".join(linhas).strip()))
                titulo_atual, linhas = linha[3:].strip(), [linha[3:].strip()]
            elif titulo_atual:
                linhas.append(linha)
        if titulo_atual:
            trechos.append(Trecho(f"{arquivo.name} > {titulo_atual}", "\n".join(linhas).strip()))
    return trechos


class Recuperador:
    def __init__(self, trechos: list[Trecho] | None = None):
        self.trechos = trechos if trechos is not None else carregar_trechos()
        self.vetorizador = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            stop_words=STOPWORDS_PT,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self.matriz = self.vetorizador.fit_transform(t.texto for t in self.trechos)

    def buscar(self, consulta: str, k: int = 4, arquivo: str | None = None) -> list[tuple[Trecho, float]]:
        """Retorna os k trechos mais relevantes com a pontuação de similaridade.
        'arquivo' (opcional) limita a busca aos trechos de arquivos que começam com esse prefixo."""
        vetor = self.vetorizador.transform([consulta])
        notas = cosine_similarity(vetor, self.matriz)[0]
        ordem = [i for i in notas.argsort()[::-1]
                 if arquivo is None or self.trechos[i].fonte.startswith(arquivo)]
        return [(self.trechos[i], float(notas[i])) for i in ordem[:k] if notas[i] > 0]

    def buscar_contexto(self, consulta: str) -> list[tuple[Trecho, float]]:
        """Busca em duas etapas: as 2 categorias mais parecidas (catálogo)
        + os 3 critérios mais parecidos (urgência, prazos e direitos)."""
        categorias = self.buscar(consulta, k=2, arquivo="01_")
        criterios = [r for r in self.buscar(consulta, k=len(self.trechos))
                     if not r[0].fonte.startswith("01_")][:3]
        return categorias + criterios
