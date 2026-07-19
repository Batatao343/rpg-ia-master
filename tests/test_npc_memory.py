"""
Memória de NPC vetorizada (Fase 2): índice FAISS namespaceado por game_id+npc_id.
Offline/determinístico via FakeEmbeddings (sem chave, sem rede). Cobre namespacing,
degradação sem embeddings e derivação de id.
"""
import hashlib
import os

import pytest
from langchain_core.embeddings import Embeddings

import rag


@pytest.fixture(autouse=True)
def _clean_embeddings_cache():
    """Impede vazamento de builders/cache fake para outros módulos de teste."""
    yield
    rag._embeddings_cache.clear()
    rag._active_provider_name = None


class FakeEmbeddings(Embeddings):
    """Embeddings determinísticos por hash do texto (dim fixa). Sem rede."""

    dim: int = 16

    def _vec(self, text: str):
        h = hashlib.sha256((text or "").encode("utf-8")).digest()
        return [b / 255.0 for b in h[: self.dim]]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def _use_fake_embeddings(monkeypatch):
    """Seam determinístico pós spec embeddings-provider: força o provider 'jina'
    (via env) e faz TODO builder devolver FakeEmbeddings — write e read passam
    pelo mesmo fake, independente de key ambiente (`_EMBEDDING_BUILDERS`/pin)."""
    monkeypatch.setenv("JINA_API_KEY", "x")
    for k in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "RPG_EMBEDDINGS"):
        monkeypatch.delenv(k, raising=False)
    rag._embeddings_cache.clear()
    rag._active_provider_name = None
    monkeypatch.setattr(rag, "_EMBEDDING_BUILDERS",
                        {p: (lambda p=p: FakeEmbeddings()) for p in rag.EMBEDDING_ROUTES})


def test_npc_memory_namespaced_per_npc(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)

    rag.add_npc_memory("g1", "npc_aldric", ["O jogador salvou a filha de Aldric em Nova Arcádia."])

    got = rag.query_npc_memory("g1", "npc_aldric", "filha salva")
    assert "filha" in got, "o próprio NPC deve recuperar seu fato"

    # Isolamento: outro NPC (sem índice) não enxerga a memória do primeiro
    assert rag.query_npc_memory("g1", "npc_bran", "filha salva") == ""
    # Isolamento por jogo: outra sessão também não enxerga
    assert rag.query_npc_memory("g2", "npc_aldric", "filha salva") == ""


def test_npc_memory_degrades_without_embeddings(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "get_embeddings", lambda: None)  # sem chave

    rag.add_npc_memory("g3", "npc_x", ["fato qualquer"])  # no-op
    assert rag.query_npc_memory("g3", "npc_x", "fato") == ""
    assert not os.path.exists(os.path.join(str(tmp_path), "g3")), "nada deve ser escrito sem embeddings"


def test_npc_memory_noop_on_missing_args(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "get_embeddings", lambda: FakeEmbeddings())
    # sem game_id/npc_id/texts → no-op, sem crash
    rag.add_npc_memory("", "npc_a", ["x"])
    rag.add_npc_memory("g", "", ["x"])
    rag.add_npc_memory("g", "npc_a", [])
    assert rag.query_npc_memory("", "npc_a", "x") == ""
    assert rag.query_npc_memory("g", "npc_a", "") == ""


def test_npc_id_stable():
    from agents.npc import _npc_id
    assert _npc_id({}, "Guarda Bran") == "npc_guarda_bran"
    assert _npc_id({"id": "npc_custom"}, "Qualquer Nome") == "npc_custom"
    assert _npc_id({}, "") == "npc_desconhecido"


def test_session_memory_survives_npc_dir(tmp_path, monkeypatch):
    """Regressão do bug faiss::FileIOReader do playtest longo (2026-07-19):
    `add_npc_memory` cria `saves_memory/{game_id}/` (pai da subpasta do NPC)
    SEM índice de sessão. `add_memory_to_session` NÃO pode confundir o dir com
    um índice existente e cair em FileIOReader — deve criar/gravar o índice."""
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)

    # NPC memory primeiro → cria tmp/g_sess/ (pai) + tmp/g_sess/npc_x/, mas o
    # índice de SESSÃO (g_sess/index.faiss) ainda não existe.
    rag.add_npc_memory("g_sess", "npc_x", ["Fato do NPC."])
    assert os.path.isdir(os.path.join(str(tmp_path), "g_sess"))
    assert not rag._has_faiss_index(os.path.join(str(tmp_path), "g_sess"))

    # Antes do fix: entrava no ramo de load → FileIOReader → memória perdida.
    rag.add_memory_to_session("g_sess", ["O portão de ferro range ao vento."])
    assert rag._has_faiss_index(os.path.join(str(tmp_path), "g_sess")), \
        "índice de sessão deve ser gravado apesar do dir criado pela memória de NPC"
    # E a subpasta do NPC segue intacta e consultável.
    assert "Fato" in rag.query_npc_memory("g_sess", "npc_x", "fato do npc")
