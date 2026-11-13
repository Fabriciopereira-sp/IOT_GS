"""Testes automatizados (rodam sem chave de API, a IA é simulada)."""
import os

os.environ["USAR_IA"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import triagem  # noqa: E402
from app.anonimizacao import anonimizar  # noqa: E402
from app.fallback import classificar_por_regras  # noqa: E402
from app.main import app  # noqa: E402
from app.rag import Recuperador  # noqa: E402
from app.schemas import TriagemRequest  # noqa: E402

cliente = TestClient(app)


# ---------- Anonimização (LGPD) ----------
def test_anonimizacao_remove_cpf_telefone_email():
    texto, removidos = anonimizar("CPF 123.456.789-00, tel (11) 98765-4321, email joao@gmail.com")
    assert "123.456.789-00" not in texto and "98765-4321" not in texto and "joao@gmail.com" not in texto
    assert set(removidos) == {"cpf", "telefone", "email"}


def test_anonimizacao_mantem_texto_sem_dados_pessoais():
    texto, removidos = anonimizar("Buraco na rua 7 de setembro, número 120")
    assert texto == "Buraco na rua 7 de setembro, número 120"
    assert removidos == []


# ---------- RAG ----------
def test_rag_recupera_categoria_certa():
    rec = Recuperador()
    melhor = rec.buscar("poste apagado e rua escura", k=1, arquivo="01_")[0][0]
    assert "iluminacao_publica" in melhor.fonte


def test_rag_traz_criterios_de_urgencia():
    fontes = [t.fonte for t, _ in Recuperador().buscar_contexto("rua alagada com água entrando nas casas")]
    assert any("alagamento" in f for f in fontes)
    assert any("02_criterios_urgencia" in f for f in fontes)


# ---------- Modo reserva ----------
@pytest.mark.parametrize("descricao, categoria, urgencia", [
    ("Rua alagada com carro ilhado", "alagamento", "alta"),
    ("Lixo acumulado há dias na esquina", "lixo_entulho", "media"),
    ("Só uma lâmpada apagada na minha rua", "iluminacao_publica", "baixa"),
    ("Meu vizinho faz barulho toda noite", "fora_do_escopo", "baixa"),
])
def test_regras(descricao, categoria, urgencia):
    assert classificar_por_regras(descricao) == (categoria, urgencia)


# ---------- Validação da resposta da IA (IA simulada) ----------
def _simular_ia(monkeypatch, resposta):
    monkeypatch.setattr(triagem.config, "ia_habilitada", lambda: True)
    monkeypatch.setattr(triagem, "chamar_gemini", lambda *a, **k: resposta)


def test_ia_resposta_valida(monkeypatch):
    _simular_ia(monkeypatch, {
        "categoria": "alagamento", "urgencia": "alta", "orgao": "Defesa Civil Municipal",
        "justificativa": "Água entrando nas casas.", "mensagem_cidadao": "Encaminhado à Defesa Civil.",
    })
    r = triagem.triar(TriagemRequest(descricao="Rua alagada, água entrando nas casas"))
    assert (r.modo, r.categoria, r.urgencia, r.prazo_sugerido) == ("ia", "alagamento", "alta", "até 24 horas")
    assert r.aviso is None


def test_ia_orgao_errado_e_corrigido(monkeypatch):
    _simular_ia(monkeypatch, {
        "categoria": "buraco_via", "urgencia": "media", "orgao": "Ministério dos Buracos",
        "justificativa": "x", "mensagem_cidadao": "y",
    })
    r = triagem.triar(TriagemRequest(descricao="Buraco médio na avenida"))
    assert r.orgao == "Secretaria Municipal de Infraestrutura e Obras"
    assert "corrigido" in r.aviso


def test_ia_categoria_inventada_vai_para_modo_reserva(monkeypatch):
    _simular_ia(monkeypatch, {"categoria": "dragao", "urgencia": "alta", "orgao": "",
                              "justificativa": "", "mensagem_cidadao": ""})
    r = triagem.triar(TriagemRequest(descricao="Buraco médio na avenida"))
    assert r.modo == "regras" and r.categoria == "buraco_via"


def test_ia_fora_do_ar_vai_para_modo_reserva(monkeypatch):
    monkeypatch.setattr(triagem.config, "ia_habilitada", lambda: True)

    def falhar(*a, **k):
        raise TimeoutError("sem internet")

    monkeypatch.setattr(triagem, "chamar_gemini", falhar)
    r = triagem.triar(TriagemRequest(descricao="Poste apagado na rua toda"))
    assert r.modo == "regras" and r.categoria == "iluminacao_publica"


def test_dados_pessoais_nao_chegam_na_ia(monkeypatch):
    recebido = {}
    monkeypatch.setattr(triagem.config, "ia_habilitada", lambda: True)

    def capturar(prompt, *a, **k):
        recebido["prompt"] = prompt
        return {"categoria": "buraco_via", "urgencia": "media",
                "orgao": "Secretaria Municipal de Infraestrutura e Obras",
                "justificativa": "x", "mensagem_cidadao": "y"}

    monkeypatch.setattr(triagem, "chamar_gemini", capturar)
    triagem.triar(TriagemRequest(descricao="Sou o João, CPF 123.456.789-00. Buraco na minha rua"))
    assert "123.456.789-00" not in recebido["prompt"]


# ---------- API ----------
def test_health():
    r = cliente.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_endpoint_triagem():
    r = cliente.post("/api/v1/triagem", json={"descricao": "Árvore caiu e bloqueou a rua toda"})
    assert r.status_code == 200
    assert r.json()["categoria"] == "arvore_risco"


def test_endpoint_rejeita_descricao_vazia():
    assert cliente.post("/api/v1/triagem", json={"descricao": ""}).status_code == 422


def test_endpoint_categorias():
    r = cliente.get("/api/v1/categorias")
    assert r.status_code == 200 and len(r.json()) == 9


def test_experimento_sem_rag_nao_envia_contexto(monkeypatch):
    recebido = {}
    monkeypatch.setattr(triagem.config, "ia_habilitada", lambda: True)

    def capturar(prompt, *a, **k):
        recebido["prompt"] = prompt
        return {"categoria": "buraco_via", "urgencia": "media",
                "orgao": "Secretaria Municipal de Infraestrutura e Obras",
                "justificativa": "x", "mensagem_cidadao": "y"}

    monkeypatch.setattr(triagem, "chamar_gemini", capturar)
    r = triagem.triar(TriagemRequest(descricao="Buraco médio na avenida"), usar_rag=False)
    assert r.fontes == [] and "Categoria buraco_via" not in recebido["prompt"]
