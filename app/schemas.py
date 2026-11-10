"""Contratos de entrada e saída da API."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class TriagemRequest(BaseModel):
    descricao: str = Field(
        ..., min_length=10, max_length=2000,
        description="Relato do cidadão sobre o problema",
        examples=["Tem um buraco enorme na Rua das Flores, perto da escola, um motoqueiro caiu ontem"],
    )
    endereco: Optional[str] = Field(None, max_length=300, description="Endereço ou referência (opcional)")
    imagem_base64: Optional[str] = Field(
        None, max_length=5_600_000, description="Foto do problema em base64 (opcional, máx. ~4 MB)")
    imagem_mime: Optional[str] = Field("image/jpeg", description="Tipo da imagem: image/jpeg ou image/png")


class TriagemResponse(BaseModel):
    categoria: str
    categoria_nome: str
    urgencia: Literal["alta", "media", "baixa"]
    orgao: str
    prazo_sugerido: str
    justificativa: str
    mensagem_cidadao: str
    fontes: list[str] = Field(description="Trechos da base de conhecimento usados (RAG)")
    modo: Literal["ia", "regras"] = Field(description="'ia' = Gemini + RAG; 'regras' = modo reserva sem IA")
    dados_pessoais_removidos: list[str] = []
    aviso: Optional[str] = None
