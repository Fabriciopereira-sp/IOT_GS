"""Configurações e catálogo fixo da triagem."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BASE_CONHECIMENTO = RAIZ / "base_conhecimento"

# Credenciais e modelo vêm do ambiente (.env). Nunca colocar a chave no código.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "60000"))
# Nível de raciocínio do modelo: "low" deixa a resposta mais rápida (classificar não exige raciocínio longo).
# Use "padrao" para não enviar essa configuração (modelos que não aceitam o parâmetro).
GEMINI_THINKING = os.getenv("GEMINI_THINKING", "low").strip().lower()


def ia_habilitada() -> bool:
    """A IA generativa só é usada se USAR_IA não for 'false' e houver chave."""
    usar = os.getenv("USAR_IA", "true").strip().lower() != "false"
    return usar and bool(GEMINI_API_KEY)


# Catálogo oficial: a resposta da IA é sempre validada contra ele.
CATEGORIAS = {
    "buraco_via": {
        "nome": "Buraco ou dano no asfalto",
        "orgao": "Secretaria Municipal de Infraestrutura e Obras",
    },
    "iluminacao_publica": {
        "nome": "Iluminação pública",
        "orgao": "Departamento de Iluminação Pública",
    },
    "alagamento": {
        "nome": "Alagamento e drenagem",
        "orgao": "Defesa Civil Municipal",
    },
    "lixo_entulho": {
        "nome": "Lixo, entulho e limpeza urbana",
        "orgao": "Departamento de Limpeza Urbana",
    },
    "arvore_risco": {
        "nome": "Árvores e áreas verdes",
        "orgao": "Secretaria Municipal do Verde e Meio Ambiente",
    },
    "calcada_acessibilidade": {
        "nome": "Calçadas e acessibilidade",
        "orgao": "Secretaria Municipal de Infraestrutura e Obras",
    },
    "sinalizacao_transito": {
        "nome": "Sinalização de trânsito",
        "orgao": "Departamento Municipal de Trânsito",
    },
    "vazamento_esgoto": {
        "nome": "Água e esgoto",
        "orgao": "Concessionária de Saneamento",
    },
    "fora_do_escopo": {
        "nome": "Fora do escopo da zeladoria",
        "orgao": "Nenhum (orientar o cidadão a procurar o canal adequado)",
    },
}

URGENCIAS = ["alta", "media", "baixa"]

PRAZOS = {
    "alta": "até 24 horas",
    "media": "até 5 dias úteis",
    "baixa": "até 15 dias úteis",
}
