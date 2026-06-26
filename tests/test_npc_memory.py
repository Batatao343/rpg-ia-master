"""
Memória de NPC vetorizada (Fase 2): índice FAISS namespaceado por game_id+npc_id.
Offline/determinístico via FakeEmbeddings (sem chave, sem rede). Cobre namespacing,
degradação sem embeddings e derivação de id.
"""
import hashlib
import os

from langchain_core.embeddings import Embeddings

import rag


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


def test_npc_memory_namespaced_per_npc(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "get_embeddings", lambda: FakeEmbeddings())

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
