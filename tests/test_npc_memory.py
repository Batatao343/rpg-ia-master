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
    rag.set_rag_operation_hook(None)
    """Impede vazamento de builders/cache fake para outros módulos de teste."""
    yield
    rag.set_rag_operation_hook(None)
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

    assert rag.add_npc_memory(
        "g1",
        "npc_aldric",
        ["O jogador salvou a filha de Aldric em Nova Arcádia."],
    ) is True

    got = rag.query_npc_memory("g1", "npc_aldric", "filha salva")
    assert "filha" in got, "o próprio NPC deve recuperar seu fato"

    # Isolamento: outro NPC (sem índice) não enxerga a memória do primeiro
    assert rag.query_npc_memory("g1", "npc_bran", "filha salva") == ""
    # Isolamento por jogo: outra sessão também não enxerga
    assert rag.query_npc_memory("g2", "npc_aldric", "filha salva") == ""


def test_npc_memory_degrades_without_embeddings(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "get_embeddings", lambda: None)  # sem chave

    assert rag.add_npc_memory("g3", "npc_x", ["fato qualquer"]) is False
    assert rag.query_npc_memory("g3", "npc_x", "fato") == ""
    assert not os.path.exists(os.path.join(str(tmp_path), "g3")), "nada deve ser escrito sem embeddings"


def test_npc_memory_noop_on_missing_args(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "get_embeddings", lambda: FakeEmbeddings())
    # sem game_id/npc_id/texts → no-op, sem crash
    assert rag.add_npc_memory("", "npc_a", ["x"]) is False
    assert rag.add_npc_memory("g", "", ["x"]) is False
    assert rag.add_npc_memory("g", "npc_a", []) is False
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
    assert rag.add_npc_memory("g_sess", "npc_x", ["Fato do NPC."]) is True
    assert os.path.isdir(os.path.join(str(tmp_path), "g_sess"))
    assert not rag._has_faiss_index(os.path.join(str(tmp_path), "g_sess"))

    # Antes do fix: entrava no ramo de load → FileIOReader → memória perdida.
    assert rag.add_memory_to_session(
        "g_sess", ["O portão de ferro range ao vento."]
    ) is True
    assert rag._has_faiss_index(os.path.join(str(tmp_path), "g_sess")), \
        "índice de sessão deve ser gravado apesar do dir criado pela memória de NPC"
    # E a subpasta do NPC segue intacta e consultável.
    assert "Fato" in rag.query_npc_memory("g_sess", "npc_x", "fato do npc")


def test_ascii_seguro_preserva_paths_legados(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))

    assert rag._get_session_path("game_123-ABC") == os.path.join(
        str(tmp_path), "game_123-ABC"
    )
    assert rag._get_npc_path("game_123-ABC", "npc_guarda_bran") == os.path.join(
        str(tmp_path), "game_123-ABC", "npc_guarda_bran"
    )


def test_unicode_usa_path_ascii_estavel_e_faz_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)
    npc_id = "npc_a_figura_pálida"

    first_path = rag._get_npc_path("g_unicode", npc_id)
    second_path = rag._get_npc_path("g_unicode", npc_id)
    physical_name = os.path.basename(first_path)

    assert first_path == second_path
    assert physical_name.isascii()
    assert physical_name != npc_id
    assert "--" in physical_name
    assert rag.add_npc_memory(
        "g_unicode", npc_id, ["A Figura Pálida guardou o juramento."]
    ) is True
    assert "juramento" in rag.query_npc_memory(
        "g_unicode", npc_id, "o que ela guardou?"
    )


def test_componentes_inseguros_nao_colidem_nem_escapam_da_raiz(
        tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))

    variants = ["CON", "..", ".", "npc/a", "npc\\a", "nome.", "nome ", "á", "ä"]
    physical = [rag._safe_storage_component(value, "npc") for value in variants]

    assert len(set(physical)) == len(physical)
    assert all(name.isascii() for name in physical)
    assert rag._safe_storage_component("á", "npc") == rag._safe_storage_component(
        "á", "npc"
    )
    for value in variants:
        path = os.path.abspath(rag._get_npc_path(value, value))
        assert os.path.commonpath([os.path.abspath(str(tmp_path)), path]) == os.path.abspath(
            str(tmp_path)
        )


def test_falha_de_escrita_retorna_false_e_emite_evento(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)
    events = []
    rag.set_rag_operation_hook(events.append)

    def _fail_save(*_args, **_kwargs):
        raise OSError("disco indisponivel")

    monkeypatch.setattr(rag, "_save_index", _fail_save)

    assert rag.add_npc_memory("g1", "npc_aria", ["um fato"]) is False
    assert len(events) == 1
    event = events[0]
    assert event.operation == "add_npc_memory"
    assert event.success is False
    assert event.game_id == "g1"
    assert event.npc_id == "npc_aria"
    assert event.facts_count == 1
    assert "disco indisponivel" in (event.error or "")


def test_sucesso_de_sessao_emite_evento_estruturado(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)
    events = []
    rag.set_rag_operation_hook(events.append)

    assert rag.add_memory_to_session("g_event", ["fato"]) is True
    assert len(events) == 1
    event = events[0]
    assert event.operation == "add_session_memory"
    assert event.success is True
    assert event.game_id == "g_event"
    assert event.npc_id is None
    assert event.provider == "jina"


def test_query_session_memory_nao_busca_lore_global(tmp_path, monkeypatch):
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    _use_fake_embeddings(monkeypatch)

    assert rag.add_memory_to_session(
        "g_only", ["A ponte da sessão foi destruída."]
    ) is True
    assert "ponte" in rag.query_session_memory("ponte", "g_only")
    assert rag.query_session_memory("ponte", "outro_jogo") == ""
