"""API de triagem inteligente de ocorrências de zeladoria (GS 2026/2 - CitizenTech)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.schemas import TriagemRequest, TriagemResponse
from app.triagem import recuperador, triar

@asynccontextmanager
async def ciclo_de_vida(_app):
    recuperador()  # indexa a base de conhecimento uma vez ao subir
    yield


app = FastAPI(
    lifespan=ciclo_de_vida,
    title="Zeladoria Colaborativa - Triagem com IA",
    description=("Recebe o relato do cidadão e devolve categoria, urgência, órgão responsável e prazo, "
                 "usando IA generativa (Gemini) com RAG sobre a base de conhecimento da prefeitura."),
    version="1.0.0",
)

# Permite que o app Mobile e a API .NET chamem este serviço.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health", tags=["Monitoramento"])
def health():
    return {
        "status": "ok",
        "ia_habilitada": config.ia_habilitada(),
        "modelo": config.GEMINI_MODEL if config.ia_habilitada() else None,
        "trechos_indexados": len(recuperador().trechos),
    }


@app.get("/api/v1/categorias", tags=["Triagem"])
def listar_categorias():
    return [{"codigo": c, **dados} for c, dados in config.CATEGORIAS.items()]


@app.post("/api/v1/triagem", response_model=TriagemResponse, tags=["Triagem"])
def triagem(pedido: TriagemRequest):
    return triar(pedido)
