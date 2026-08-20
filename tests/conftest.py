"""Config de testes: força o modo simulado (MockLLM) para a suíte ser
determinística e offline — independente de haver GOOGLE_API_KEY no ambiente
(evita falhas por quota/rede). O comportamento de jogo real não muda."""
import os

import pytest

# Precisa estar setado antes de qualquer chamada a get_llm() nos nós do grafo.
os.environ.setdefault("RPG_FORCE_MOCK", "1")
# Fase 10: rate limit da API desligado na suíte (TestClient compartilha IP).
os.environ.setdefault("RPG_RATE_LIMIT", "0")


@pytest.fixture(autouse=True)
def _isolated_runtime_cache(monkeypatch, tmp_path):
    """spec isolar-cache-runtime (R5): caches gerados em runtime (bestiário
    gerado, NPC db, artefatos custom) vão p/ tmp — a suíte NUNCA suja data/
    (antes: entradas mock em bestiary/npc_database exigiam git checkout)."""
    monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path / "runtime"))
    from infrastructure.runtime import reset_runtime

    reset_runtime()
    yield
    reset_runtime()


@pytest.fixture(autouse=True)
def _isolated_saves_and_memory(monkeypatch, tmp_path):
    """Todo teste usa saves/checkpoints/memória descartáveis.

    Rotas TestClient anteriormente escreviam centenas de campanhas ``Streamer``
    nos diretórios reais ignorados pelo git. O sandbox é global porque salvar é
    efeito colateral transversal do grafo, não responsabilidade de cada teste.
    """
    import persistence
    import rag

    saves_dir = tmp_path / "saves"
    memory_dir = tmp_path / "saves_memory"
    monkeypatch.setattr(persistence, "SAVES_DIR", str(saves_dir))
    monkeypatch.setattr(persistence, "SESSION_MEMORY_DIR", str(memory_dir))
    monkeypatch.setattr(rag, "SAVES_DIR", str(memory_dir))


@pytest.fixture(autouse=True)
def _no_real_embeddings(monkeypatch, request):
    """Desliga embeddings REAIS na suíte offline. Com uma key viva no `.env`
    (ex.: Jina desde a spec embeddings-provider), `query_rag`/archivist
    baterlam na API de verdade — rede, custo, rate limit. Aqui todo teste vê
    embeddings desativados (RAG devolve "", writes viram no-op), igual ao
    comportamento histórico (Google 429). Os módulos que exercitam a cadeia de
    embeddings gerenciam o próprio seam e ficam de fora."""
    if any(m in request.node.nodeid for m in ("test_embeddings_provider", "test_npc_memory")):
        return
    import rag
    monkeypatch.setattr(rag, "get_embeddings", lambda: None, raising=False)
    monkeypatch.setattr(rag, "_embeddings_for_index", lambda _p: None, raising=False)
