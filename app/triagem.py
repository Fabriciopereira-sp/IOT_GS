"""Orquestra a triagem: anonimização -> RAG -> IA generativa -> validação (ou modo reserva)."""
import logging

from app import config
from app.anonimizacao import anonimizar
from app.fallback import classificar_por_regras
from app.llm import chamar_gemini, montar_prompt
from app.rag import Recuperador
from app.schemas import TriagemRequest, TriagemResponse

log = logging.getLogger("triagem")
_recuperador: Recuperador | None = None


def recuperador() -> Recuperador:
    global _recuperador
    if _recuperador is None:
        _recuperador = Recuperador()
    return _recuperador


def _prazo(categoria: str, urgencia: str) -> str:
    return "não se aplica" if categoria == "fora_do_escopo" else config.PRAZOS[urgencia]


def _resposta_por_regras(descricao: str, fontes: list[str], removidos: list[str], aviso: str) -> TriagemResponse:
    categoria, urgencia = classificar_por_regras(descricao)
    info = config.CATEGORIAS[categoria]
    if categoria == "fora_do_escopo":
        mensagem = ("Seu relato não parece ser um problema de espaço público atendido pela zeladoria. "
                    "Em emergência com risco à vida, ligue 190, 193, 192 ou 199.")
        justificativa = "Nenhuma palavra-chave de zeladoria encontrada no relato."
    else:
        mensagem = (f"Recebemos seu relato sobre {info['nome'].lower()}. Ele foi encaminhado para "
                    f"{info['orgao']} com prazo de atendimento {config.PRAZOS[urgencia]}.")
        justificativa = f"Classificação por palavras-chave (modo reserva): urgência {urgencia}."
    return TriagemResponse(
        categoria=categoria, categoria_nome=info["nome"], urgencia=urgencia, orgao=info["orgao"],
        prazo_sugerido=_prazo(categoria, urgencia), justificativa=justificativa,
        mensagem_cidadao=mensagem, fontes=fontes, modo="regras",
        dados_pessoais_removidos=removidos, aviso=aviso,
    )


def triar(pedido: TriagemRequest, usar_rag: bool = True) -> TriagemResponse:
    """usar_rag=False existe só para o experimento de avaliação (IA sem a base de conhecimento)."""
    descricao, removidos = anonimizar(pedido.descricao.strip())
    endereco = anonimizar(pedido.endereco)[0] if pedido.endereco else None

    trechos = recuperador().buscar_contexto(descricao) if usar_rag else []
    fontes = [t.fonte for t, _ in trechos]
    contexto = ("\n\n---\n\n".join(f"[{t.fonte}]\n{t.texto}" for t, _ in trechos)
                or "(sem contexto: decida com seu conhecimento geral)")

    if not config.ia_habilitada():
        return _resposta_por_regras(descricao, fontes, removidos,
                                    "IA generativa desativada ou sem chave configurada; usado o modo reserva.")

    try:
        bruto = chamar_gemini(montar_prompt(descricao, endereco, contexto),
                              pedido.imagem_base64, pedido.imagem_mime)
    except Exception as erro:  # sem internet, limite da API, JSON inválido, etc.
        log.warning("Falha na IA, usando modo reserva: %s", erro)
        motivo = str(erro).split(".")[0][:80]
        return _resposta_por_regras(descricao, fontes, removidos,
                                    f"A IA não respondeu ({motivo}); usado o modo reserva por regras.")

    # Validação da saída da IA contra o catálogo oficial (a IA nunca tem a palavra final sozinha).
    categoria = bruto.get("categoria")
    urgencia = bruto.get("urgencia")
    if categoria not in config.CATEGORIAS or urgencia not in config.URGENCIAS:
        return _resposta_por_regras(descricao, fontes, removidos,
                                    "A IA devolveu uma resposta fora do catálogo; usado o modo reserva.")

    aviso = None
    orgao_oficial = config.CATEGORIAS[categoria]["orgao"]
    if bruto.get("orgao", "").strip().lower() != orgao_oficial.lower():
        aviso = f"Órgão sugerido pela IA ('{bruto.get('orgao')}') corrigido pelo catálogo oficial."
    if categoria == "fora_do_escopo":
        urgencia = "baixa"

    return TriagemResponse(
        categoria=categoria,
        categoria_nome=config.CATEGORIAS[categoria]["nome"],
        urgencia=urgencia,
        orgao=orgao_oficial,
        prazo_sugerido=_prazo(categoria, urgencia),
        justificativa=str(bruto.get("justificativa", "")).strip(),
        mensagem_cidadao=str(bruto.get("mensagem_cidadao", "")).strip(),
        fontes=fontes,
        modo="ia",
        dados_pessoais_removidos=removidos,
        aviso=aviso,
    )
