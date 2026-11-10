"""Remove dados pessoais do texto antes de enviar para a IA (LGPD)."""
import re

_PADROES = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("[CPF]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("[TELEFONE]", re.compile(r"(?:\(?\b\d{2}\)?[\s-]?)?\b9?\d{4}[\s-]?\d{4}\b")),
]


def anonimizar(texto: str) -> tuple[str, list[str]]:
    """Retorna o texto mascarado e a lista de tipos de dado removidos."""
    removidos = []
    for marcador, padrao in _PADROES:
        texto, quantidade = padrao.subn(marcador, texto)
        if quantidade:
            removidos.append(marcador.strip("[]").lower())
    return texto, removidos
