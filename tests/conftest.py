"""Config de testes: força o modo simulado (MockLLM) para a suíte ser
determinística e offline — independente de haver GOOGLE_API_KEY no ambiente
(evita falhas por quota/rede). O comportamento de jogo real não muda."""
import os

import pytest

# Precisa estar setado antes de qualquer chamada a get_llm() nos nós do grafo.
os.environ.setdefault("RPG_FORCE_MOCK", "1")
# Fase 10: rate limit da API desligado na suíte (TestClient compartilha IP).
os.environ.setdefault("RPG_RATE_LIMIT", "0")
# SPEC-239: records de rpg.* propagam ao root para o caplog ver.
os.environ.setdefault("RPG_LOG_PROPAGATE", "1")
# SPEC-194: HMAC key for Play obfuscated account ids (tests that need it absent delenv it).
os.environ.setdefault("RPG_PLAY_ACCOUNT_KEY", "test-play-account-key-0123456789abcdef")


# SPEC-218 R10: marcadores de plataforma/bind do ambiente do dev/CI nunca vazam para a suíte.
_EXPOSURE_ENV = ("VERCEL", "PORT", "RAILWAY_ENVIRONMENT", "RENDER", "K_SERVICE", "FLY_APP_NAME",
                 "DYNO", "RPG_BIND_HOST", "RPG_HOST", "RPG_ALLOW_LEGACY_EXPOSED")
# Revisao Astra: limpar TAMBEM no import do conftest — `import api` acontece na coleta
# (antes de qualquer fixture), e o boot policy roda no import do api.
for _name in _EXPOSURE_ENV:
    os.environ.pop(_name, None)


@pytest.fixture(autouse=True)
def _no_exposure_markers(monkeypatch):
    for name in _EXPOSURE_ENV:
        monkeypatch.delenv(name, raising=False)


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


@pytest.fixture(autouse=True)
def _force_request_rls(monkeypatch):
    """SPEC-224: `RPG_TEST_REQUEST_RLS=1` roda toda a suite infra_local com RLS efetivo por request
    (qualquer PostgresPool criado com principal ativo assume `rpg_api`), para provar que nenhum
    caminho de usuario depende de privilegio alem do que `rpg_api` tem."""
    if os.getenv("RPG_TEST_REQUEST_RLS") != "1":
        yield
        return
    from infrastructure.postgres import PostgresPool

    original = PostgresPool.__init__

    def patched(self, *args, **kwargs):
        kwargs["request_rls"] = True
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PostgresPool, "__init__", patched)

    # Os testes locais passam o principal como ARGUMENTO dos stores (sem middleware): reproduz o que a
    # API faz, abrindo o escopo de request em volta de cada metodo que recebe `principal`.
    import functools
    import inspect

    from infrastructure.request_context import principal_scope

    def scoped(fn):
        params = list(inspect.signature(fn).parameters)

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            principal = kwargs.get("principal")
            if principal is None and "principal" in params:
                index = params.index("principal")
                principal = args[index - 1] if index - 1 < len(args) else None
            if principal is None and args:
                principal = getattr(args[0], "principal", None)  # intents/queries de memoria
            if principal is None or not hasattr(principal, "user_id"):
                return fn(self, *args, **kwargs)
            with principal_scope(principal):
                return fn(self, *args, **kwargs)
        return wrapper

    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore
    from infrastructure.postgres_turns import PostgresTurnCoordinator
    from services.chronicle_repository import ChronicleRepository

    # complete/fail/heartbeat/is_completed recebem so o `claim`: no request real o principal ja esta no
    # ContextVar desde o `claim`; aqui o lembramos por operation_id.
    claim_principals: dict = {}
    original_claim = PostgresTurnCoordinator.claim

    def remembering_claim(self, principal, operation_id, **kwargs):
        claim_principals[operation_id] = principal
        with principal_scope(principal):
            return original_claim(self, principal, operation_id, **kwargs)

    monkeypatch.setattr(PostgresTurnCoordinator, "claim", remembering_claim)

    def claim_scoped(fn):
        @functools.wraps(fn)
        def wrapper(self, claim, *args, **kwargs):
            principal = claim_principals.get(claim.operation_id)
            if principal is None:
                return fn(self, claim, *args, **kwargs)
            with principal_scope(principal):
                return fn(self, claim, *args, **kwargs)
        return wrapper

    for name in ("complete", "fail", "heartbeat", "is_completed"):
        monkeypatch.setattr(PostgresTurnCoordinator, name, claim_scoped(getattr(PostgresTurnCoordinator, name)))

    for cls, names in (
        (PostgresGameStore, ("create", "get", "list", "save", "delete", "save_checkpoint", "get_checkpoint")),
        (PostgresTurnCoordinator, ("commit_game", "commit_create", "commit_delete", "receipt")),
        (PgVectorMemoryStore, ("stage", "query")),
        (ChronicleRepository, ("append", "compress", "search")),
    ):
        for name in names:
            if hasattr(cls, name):
                monkeypatch.setattr(cls, name, scoped(getattr(cls, name)))
    yield
