"""SPEC-234 - memoria/RAG/arquivista: resiliencia a indice indisponivel,
segredos por ID de entidade, override de embeddings, resumo nunca vazio."""
from __future__ import annotations

import json
import pathlib

from agents import archivist
from agents.archivist import MemoryUpdate
from services.chronicle_search import ChronicleCandidate, search_chronicle
from services.context_builder import build_context_pack
from services.memory_provenance import (
    accepted_secret_ids,
    find_strict_unrevealed,
    make_memory_fact,
    validate_memory_fact,
)
from services.secret_signatures import SECRET_ENTITY_IDS, SECRET_SIGNATURES


class _LLM:
    is_fallback = False

    def __init__(self, summary="Resumo do turno"):
        self.calls = 0
        self.summary = summary

    def with_structured_output(self, _schema):
        outer = self

        class _S:
            def invoke(self, _m):
                outer.calls += 1
                return MemoryUpdate(
                    new_summary=f"{outer.summary} {outer.calls}",
                    important_facts=[f"Fato distinto numero {outer.calls}."],
                    chronicle_entry="",
                )
        return _S()


def _state(turn, **extra):
    base = {
        "game_id": "mem-res", "world": {"turn_count": turn},
        "messages": [], "narrative_summary": "Antes.", "archive_due": True,
    }
    base.update(extra)
    return base


# --- R1 -------------------------------------------------------------------
def test_archivist_continues_when_index_fails(monkeypatch):
    llm = _LLM()
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: llm)
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: False)
    state = _state(1)
    for turn in (1, 2, 3):
        state = {**state, "world": {"turn_count": turn}}
        state = {**state, **archivist.archive_node(state)}
    assert llm.calls == 3
    assert state["narrative_summary"] == "Resumo do turno 3"
    assert len(state["memory_facts"]) == 3
    assert {f["vector_status"] for f in state["memory_facts"]} == {"pending"}
    assert len(state["pending_memory_facts"]) == 3
    assert state["archivist_last_run"] == 3


def test_archivist_index_down_emits_degraded_metric(monkeypatch):
    from observability.metrics import metrics

    def _count():
        return sum(v for k, v in metrics.snapshot().items()
                   if "rpg_rag_degraded_total" in k and "session_write" in k)

    llm = _LLM()
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: llm)
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: False)
    before = _count()
    state = {**_state(1), "world": {"turn_count": 1}}
    archivist.archive_node(state)
    assert _count() == before + 1


def test_pending_vector_writes_flushed_in_retry_window(monkeypatch):
    llm = _LLM()
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: llm)
    ok = {"v": False}
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: ok["v"])
    state = _state(1)
    state = {**state, **archivist.archive_node(state)}
    ok["v"] = True
    state = {**state, "world": {"turn_count": 3}}
    state = {**state, **archivist.archive_node(state)}
    assert state["pending_memory_facts"] == []
    assert {f["vector_status"] for f in state["memory_facts"]} == {"written"}


# --- R2 -------------------------------------------------------------------
def test_context_uses_ledger_when_index_down(monkeypatch):
    from services import context_builder

    monkeypatch.setattr(context_builder, "query_rag", lambda *_a, **_k: "")
    monkeypatch.setattr(context_builder, "query_session_memory", lambda *_a, **_k: "")
    fact = make_memory_fact("A ponte de Brekmar caiu.", provenance="player_observation",
                            source_id="obs:1", source_turn=2)
    fact["vector_status"] = "pending"
    pack = build_context_pack(
        {"world": {"turn_count": 3}, "npcs": {}, "memory_facts": [fact]},
        "ponte", "story", game_id="g",
    )
    assert "ponte de Brekmar" in pack.memory_block


# --- R3 -------------------------------------------------------------------
def test_secret_revealed_by_entity_id_unlocks():
    reveal = {"event_id": "e1", "type": "secret_revealed", "turn": 3,
              "target_id": "mon_rei_subterraneo", "payload": {}}
    state = {"event_log": [reveal]}
    text = "O verme-primordial das raízes do mundo desperta."
    assert find_strict_unrevealed(text, {"event_log": []}) == "rei_subterraneo"
    assert find_strict_unrevealed(text, state) is None
    assert "rei_subterraneo" in accepted_secret_ids(state)
    fact = make_memory_fact(text, provenance="canonical_event",
                            source_id="e1", source_turn=3)
    accepted, reason = validate_memory_fact(fact, state)
    assert reason is None and accepted is not None


def test_secret_entity_ids_exist_in_graph():
    entities = json.loads(
        pathlib.Path("data/graph/entities.json").read_text(encoding="utf-8"))
    rows = entities if isinstance(entities, list) else list(entities.values())
    ids = {e["id"] for e in rows}
    assert set(SECRET_ENTITY_IDS) == set(SECRET_SIGNATURES)
    for secret, entity_ids in SECRET_ENTITY_IDS.items():
        assert entity_ids and entity_ids <= ids, secret


def test_revealed_corpus_reads_revealed_facts():
    from services.secret_signatures import revealed_corpus

    state = {"world_projection": {"revealed_facts": {"x": {"fact": "Pacto Com Valerius"}}}}
    assert "pacto com valerius" in revealed_corpus(state)


# --- R5 -------------------------------------------------------------------
def test_summary_never_empty_or_error(monkeypatch):
    class _Fallback:
        is_fallback = True

        def with_structured_output(self, _s):
            return self

        def invoke(self, _m):
            from langchain_core.messages import AIMessage
            return AIMessage(content="Erro: nenhum provider configurado.")

    monkeypatch.setattr(archivist, "get_llm", lambda **_k: _Fallback())
    monkeypatch.setattr(archivist, "add_memory_to_session", lambda *_a, **_k: True)
    out = archivist.archive_node(_state(5, narrative_summary="A vila dorme."))
    summary = out.get("narrative_summary", "A vila dorme.")
    assert summary and "Erro" not in summary
    assert summary.startswith("A vila dorme")


# --- R6 -------------------------------------------------------------------
def test_controller_by_id_without_hidden_leak(monkeypatch):
    from services import context_builder

    monkeypatch.setattr(context_builder, "query_rag", lambda *_a, **_k: "")
    monkeypatch.setattr(context_builder, "query_session_memory", lambda *_a, **_k: "")
    state = {"world": {"current_location": "Montanhas Afiadas",
                       "current_location_id": "montanhas_afiadas", "turn_count": 1},
             "npcs": {}}
    narrator = build_context_pack(state, "montanhas", "story", game_id=None)
    planner = build_context_pack(state, "montanhas", "planning", game_id=None)
    all_narrator = narrator.world_state_block + narrator.memory_block
    all_planner = planner.world_state_block + planner.memory_block
    assert "Rei Subterr" not in all_narrator
    assert "Rei Subterr" in all_planner


# --- R7 -------------------------------------------------------------------
def test_search_chronicle_stale_candidate():
    chronicle = [{"chapter_id": "c1", "title": "T", "started_turn": 1,
                  "entries": [{"entry_id": "c1:e1", "text": "A ponte caiu.", "turn": 1,
                               "kind": "prose"}]}]
    stale = [ChronicleCandidate("c1:digest", "c1", "digest", 0.9)]
    out = search_chronicle(chronicle, "ponte", semantic=stale)
    assert all(hit["chapter_id"] == "c1" for hit in out["hits"])


# --- R8 -------------------------------------------------------------------
def test_memory_budget_prefers_recent_and_relevant(monkeypatch):
    from services import context_builder

    monkeypatch.setattr(context_builder, "query_rag", lambda *_a, **_k: "")
    monkeypatch.setattr(context_builder, "query_session_memory",
                        lambda *_a, **_k: "[RELEVANTE] O mercador guarda a chave.")
    facts = [make_memory_fact(f"Fato antigo numero {i} sobre coisas variadas e longas " * 3,
                              provenance="player_observation", source_id=f"o:{i}",
                              source_turn=i) for i in range(1, 21)]
    pack = build_context_pack(
        {"world": {"turn_count": 25}, "npcs": {}, "memory_facts": facts},
        "mercador", "story", token_budget=1500, game_id="g",
    )
    assert "RELEVANTE" in pack.memory_block
    assert "numero 20 " in pack.memory_block


# --- R11 ------------------------------------------------------------------
def test_validate_narrative_preserves_paragraphs():
    from services.narrative_evidence import build_evidence, validate_narrative

    evidence = build_evidence({"world": {"turn_count": 1}})
    text = "Primeira frase.\n\nSegunda frase."
    assert validate_narrative(text, evidence, channel="message").text == text


# --- R9 / R10 -------------------------------------------------------------
def test_embedding_profile_id_and_dimension_guard():
    import pytest

    import rag

    assert rag.embedding_profile_id("jina") == "jina-jina-embeddings-v3-1024"
    assert rag.embedding_profile_id("ollama") == "ollama-bge-m3-1024"
    rag.validate_pgvector_provider("jina")
    with pytest.raises(ValueError, match="3072"):
        rag.validate_pgvector_provider("gemini")


def test_pgvector_rejects_wrong_dimension_and_isolates_profiles():
    import pytest

    from infrastructure.pgvector_memory import PgVectorMemoryStore, vector_literal

    with pytest.raises(ValueError):
        PgVectorMemoryStore(object(), dimensions=768)
    with pytest.raises(ValueError):
        vector_literal([0.1] * 768)

    class _Conn:
        def __init__(self):
            self.sql = []

        def execute(self, sql, params=()):
            self.sql.append((sql, params))
            return self

        rowcount = 3

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def transaction(self):
            return self

    conn = _Conn()

    class _Pool:
        def connection(self):
            return conn

    store = PgVectorMemoryStore(_Pool(), profile_id="jina-jina-embeddings-v3-1024")
    assert store.migrate_legacy_profile() == 3
    assert any("insert into app.embedding_profiles" in q for q, _ in conn.sql)
    assert any(p == ("jina-jina-embeddings-v3-1024", "local-1024") for _, p in conn.sql)
    # consulta com perfil diferente do adapter e recusada
    from infrastructure.contracts import MemoryQuery
    with pytest.raises(ValueError, match="incompat"):
        store.query(MemoryQuery(text="", scope="lore", vector=(0.0,) * 1024,
                                embedding_profile_id="outro-perfil"))


def test_rag_degraded_metric_emitted(monkeypatch, tmp_path):
    import rag
    from observability.metrics import metrics

    before = metrics.snapshot().get("rpg_rag_degraded_total{'source': 'session'}", 0)
    monkeypatch.setattr(rag, "SAVES_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "_has_faiss_index", lambda _p: True)
    monkeypatch.setattr(rag, "_embeddings_for_index", lambda _p: object())

    def boom(*_a, **_k):
        raise RuntimeError("indice corrompido")

    monkeypatch.setattr(rag.FAISS, "load_local", boom)
    assert rag.query_session_by_vector([0.1] * 8, "g") == ""
    after = metrics.snapshot().get("rpg_rag_degraded_total{'source': 'session'}", 0)
    assert after == before + 1


# --- Revisão Sol (SPEC-234) -------------------------------------------------
def test_pending_vector_survives_save_reload_and_flushes_once(monkeypatch):
    """Índice fora: fatos pendentes sobrevivem a save/reload, retry só na janela
    de 3 turnos, flush grava cada fato UMA vez e o ledger não duplica."""
    import persistence

    llm = _LLM()
    monkeypatch.setattr(archivist, "get_llm", lambda **_k: llm)
    ok = {"v": False}
    writes: list = []

    def _add(_gid, docs, *_a, **_k):
        if ok["v"]:
            writes.extend(docs if isinstance(docs, list) else [docs])
        return ok["v"]

    monkeypatch.setattr(archivist, "add_memory_to_session", _add)
    state = _state(1)
    for turn in (1, 2):
        state = {**state, "world": {"turn_count": turn}}
        state = {**state, **archivist.archive_node(state)}
    assert len(state["pending_memory_facts"]) == 2

    saved = json.loads(json.dumps(persistence._state_to_save_data(state, "mem-res")))
    reloaded = persistence._raw_to_state(saved)
    assert [f["memory_id"] for f in reloaded["pending_memory_facts"]] == [
        f["memory_id"] for f in state["pending_memory_facts"]
    ]
    assert {f["vector_status"] for f in reloaded["memory_facts"]} == {"pending"}

    state = {**state, **{k: reloaded[k] for k in ("memory_facts", "pending_memory_facts")}}
    ok["v"] = True
    # turno 4: fora da janela -> nenhum retry dos pendentes antigos
    state = {**state, "world": {"turn_count": 4}}
    state = {**state, **archivist.archive_node(state)}
    pending_ids = {f["memory_id"] for f in state["pending_memory_facts"]}
    assert len(pending_ids) == 2
    # turno 6: janela -> flush
    state = {**state, "world": {"turn_count": 6}}
    state = {**state, **archivist.archive_node(state)}
    assert state["pending_memory_facts"] == []
    texts = [f["text"] for f in state["memory_facts"]]
    assert len(texts) == len(set(texts)) == 4
    assert {f["vector_status"] for f in state["memory_facts"]} == {"written"}
    written_texts = [getattr(d, "page_content", str(d)) for d in writes]
    assert len(written_texts) == len(set(written_texts))


def test_payload_secret_id_cannot_unlock_other_secret():
    """Só o `target_id` validado libera segredo; ids no payload vêm do LLM."""
    reveal = {"event_id": "e1", "type": "secret_revealed", "turn": 3,
              "target_id": "mon_rede_carmesim",
              "payload": {"secret_id": "rei_subterraneo", "id": "npc_valerius"}}
    ids = accepted_secret_ids({"event_log": [reveal]})
    assert "rede_carmesim" in ids
    assert "rei_subterraneo" not in ids and "pacto_valerius" not in ids
    text = "O verme-primordial das raízes do mundo desperta."
    assert find_strict_unrevealed(text, {"event_log": [reveal]}) == "rei_subterraneo"


def test_configured_profile_is_shared_by_every_adapter(monkeypatch):
    """Turno, worker e consulta usam o MESMO perfil (senão set_embedding dá Conflict)."""
    from infrastructure.pgvector_memory import configured_profile_id

    monkeypatch.setenv("RPG_EMBEDDINGS", "jina")
    assert configured_profile_id() == "jina-jina-embeddings-v3-1024"
    import inspect

    from infrastructure import postgres_turns

    src = inspect.getsource(postgres_turns)
    assert "PgVectorMemoryStore(self.pool)" not in src
    assert src.count("profile_id=configured_profile_id()") == 2


def test_pending_facts_only_reopen_archivist_in_retry_window():
    base = {"pending_memory_facts": [{"memory_id": "m1"}], "archivist_last_run": 4}
    assert archivist._should_archive(base, 5) is False
    assert archivist._should_archive(base, 6) is True
