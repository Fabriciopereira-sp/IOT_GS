"""Modo reserva por regras: usado quando a IA está indisponível (sem internet, sem chave,
erro ou limite da API). Garante que a solução continue útil fora do cenário ideal."""
import unicodedata

PALAVRAS_CATEGORIA = {
    "alagamento": ["alag", "enchente", "inund", "transbord", "boca de lobo", "nao escoa", "deslizamento", "ilhad"],
    "vazamento_esgoto": ["esgoto", "vazamento", "vazando", "cano", "estourou", "mau cheiro de esgoto"],
    "iluminacao_publica": ["poste", "lampada", "iluminacao", "escur", "apagad", "fio", "piscando"],
    "sinalizacao_transito": ["semaforo", "farol", "placa", "faixa de pedestre", "sinalizacao", "lombada"],
    "arvore_risco": ["arvore", "galho", "poda", "mato alto", "tronco"],
    "lixo_entulho": ["lixo", "entulho", "coleta", "sofa", "descarte", "animal morto", "sujeira", "terreno baldio"],
    "calcada_acessibilidade": ["calcada", "rampa", "cadeirante", "piso tatil", "acessibilidade"],
    "buraco_via": ["buraco", "cratera", "asfalto", "afund", "bueiro", "pista"],
}

# A ordem acima importa no desempate: termos mais específicos vêm primeiro.

SINAIS_ALTA = [
    "fio", "choque", "poste caiu", "poste caido", "caiu", "caida", "acidente", "ferid",
    "ilhad", "entrando", "transbord", "deslizamento", "cratera", "sem tampa", "sumiu a tampa",
    "semaforo apagado", "farol apagado", "risco", "desab",
]
SINAIS_BAIXA = [
    "uma lampada", "so uma", "desbotad", "apagada a faixa", "pequen", "mato alto", "poda",
    "pichac", "estetic",
]
AGRAVANTES = ["escola", "creche", "hospital", "posto de saude", "ponto de onibus", "idos", "crianca", "cadeirante"]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def classificar_por_regras(descricao: str) -> tuple[str, str]:
    """Retorna (categoria, urgencia) usando palavras-chave."""
    texto = _normalizar(descricao)

    pontos = {
        categoria: sum(1 for termo in termos if termo in texto)
        for categoria, termos in PALAVRAS_CATEGORIA.items()
    }
    melhor = max(pontos, key=pontos.get)
    categoria = melhor if pontos[melhor] > 0 else "fora_do_escopo"

    if categoria == "fora_do_escopo":
        return categoria, "baixa"

    if any(s in texto for s in SINAIS_ALTA):
        urgencia = "alta"
    elif any(s in texto for s in SINAIS_BAIXA):
        urgencia = "baixa"
    else:
        urgencia = "media"

    if urgencia != "alta" and any(a in texto for a in AGRAVANTES):
        urgencia = "media" if urgencia == "baixa" else "alta"

    return categoria, urgencia
