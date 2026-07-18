"""Suíte da spec embeddings-provider (cadeia multi-provider + pin por índice).

Tudo offline: usa embedding fake determinístico (sem rede). A cadeia de
resolução é controlada por env keys (monkeypatch), o builder por um registro
fake. Ver specs/embeddings-provider.md.
"""
import hashlib
import json
import os

import pytest
from langchain_core.embeddings import Embeddings

import rag


class FakeEmbeddings(Embeddings):
    """Embedding determinístico e offline. `tag` identifica o provider fake
    (para asserts de pin por índice). Subclasse de Embeddings para o FAISS
    reconhecer (senão ele trata o objeto como função e quebra)."""

    def __init__(self, tag: str = "fake", dims: int = 8):
        self.tag = tag
        self.dims = dims

    def _vec(self, text: str):
        h = hashlib.sha256(f"{self.tag}:{text}".encode("utf-8")).digest()
        return [h[i % len(h)] / 255.0 for i in range(self.dims)]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


_ALL_KEYS = ["JINA_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "RPG_EMBEDDINGS"]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Zera cache/estado e limpa TODAS as env keys de embedding antes de cada
    teste — cada caso declara explicitamente o que existe."""
    rag._embeddings_cache.clear()
    rag._active_provider_name = None
    for k in _ALL_KEYS:
        monkeypatch.delenv(k, raising=False)
    # Registro fake: builder por provider devolve um FakeEmbeddings marcado.
    fake = {p: (lambda p=p: FakeEmbeddings(tag=p)) for p in rag.EMBEDDING_ROUTES}
    monkeypatch.setattr(rag, "_EMBEDDING_BUILDERS", fake)
    yield
    rag._embeddings_cache.clear()
    rag._active_provider_name = None


# --- Etapa 1: cadeia de resolução -------------------------------------------

def test_cadeia_resolve_primeiro_com_key(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    assert rag._resolve_provider() == "jina"


def test_gemini_so_assume_sem_nenhum_outro(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    assert rag._resolve_provider() == "gemini"


def test_openai_vence_gemini(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    assert rag._resolve_provider() == "openai"


def test_sem_key_nenhuma_desativa(monkeypatch):
    # R4: nenhum candidato disponível → resolução None → embeddings desativados.
    assert rag._resolve_provider() is None
    assert rag.get_embeddings() is None


def test_override_rpg_embeddings_forca_provider(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "x")          # jina seria o primário
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("RPG_EMBEDDINGS", "openai")   # força openai
    assert rag._resolve_provider() == "openai"
    emb = rag.get_embeddings()
    assert isinstance(emb, FakeEmbeddings) and emb.tag == "openai"
    assert rag.active_provider() == "openai"


# --- Etapa 1: meta por índice + pin -----------------------------------------

def test_meta_round_trip(tmp_path):
    rag._write_meta(str(tmp_path), "jina")
    meta = rag._read_meta(str(tmp_path))
    assert meta["provider"] == "jina"
    assert meta["model"] == rag._PROVIDER_MODELS["jina"]


def test_meta_e_gravada_ao_criar_indice(tmp_path, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "x")
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    rag.add_memory_to_session("sess1", ["fato um", "fato dois"])
    meta = rag._read_meta(str(tmp_path / "sess1"))
    assert meta is not None and meta["provider"] == "jina"


def test_indice_pinado_usa_provider_da_meta(tmp_path, monkeypatch):
    # Primário = jina, mas índice foi gerado com gemini → consulta via gemini.
    monkeypatch.setenv("JINA_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    rag._write_meta(str(tmp_path), "gemini")
    emb = rag._embeddings_for_index(str(tmp_path))
    assert isinstance(emb, FakeEmbeddings) and emb.tag == "gemini"


def test_meta_indisponivel_desativa_indice_com_warning(tmp_path, monkeypatch, caplog):
    # Índice pinado em gemini, mas GOOGLE_API_KEY sumiu → índice desativado.
    rag._write_meta(str(tmp_path), "gemini")  # sem GOOGLE_API_KEY no ambiente
    with caplog.at_level("WARNING", logger="rpg.rag"):
        emb = rag._embeddings_for_index(str(tmp_path))
    assert emb is None
    assert any("reindex" in r.message.lower() or "indispon" in r.message.lower()
               for r in caplog.records)


def test_indice_legado_sem_meta_assume_gemini(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    # tmp_path sem embeddings_meta.json → comportamento histórico (gemini).
    emb = rag._embeddings_for_index(str(tmp_path))
    assert isinstance(emb, FakeEmbeddings) and emb.tag == "gemini"


# --- Etapa 2: builder real do Jina (sem rede) -------------------------------

def test_jina_builder_sem_key_desativa(monkeypatch):
    # Builder real: sem JINA_API_KEY, jina fica indisponível na cadeia.
    monkeypatch.setattr(rag, "_EMBEDDING_BUILDERS", rag._default_builders())
    assert rag._provider_available("jina") is False


# --- Round-trip ingest→query com fake, ponta a ponta ------------------------

def test_ingest_e_query_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "x")
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    rag.add_memory_to_session("g", ["O dragão dorme na Montanha Cinza."])
    out = rag.query_rag("onde dorme o dragão?", index_name="lore", game_id="g")
    assert "dragão" in out
