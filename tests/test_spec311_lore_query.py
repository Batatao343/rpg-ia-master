"""SPEC-311 Etapa 1 — RAG de lore contextual (R17-R25)."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

import rag
from services import lore_query as lq
from services import world_calendar
from services.context_builder import ContextBudget, assemble_pack
from tests.spec309_helpers import world_state_two_regions


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _skall(season: str | None = "inverno") -> dict:
    st = world_state_two_regions(season=season)
    st["world"]["season"] = {"id": season, "label": season, "day_in_season": 1} if season else None
    if not season:
        st["world"].pop("season")
    return st


# --- R17: query composta -----------------------------------------------------------------
def test_compose_lore_query_order_and_parts():
    """R17: local · (região idêntica omitida) · estação · base; local e região entram 1x."""
    st = _skall("inverno")
    q = lq.compose_lore_query(st, "procuro a forja")
    season = world_calendar.label_for("inverno", "skallgard")
    assert q.startswith("Skallgard ")
    assert q.count("Skallgard") == 1
    assert season in q and q.endswith("procuro a forja")
    assert q.index(season) < q.index("procuro a forja")


def test_compose_lore_query_includes_public_state_label_only_with_engine_on(monkeypatch):
    """R17.3: rótulo público do estado do LOCAL ATUAL, só com motor on."""
    st = _skall(None)
    st["world_projection"]["location_states"]["skallgard"] = {"state": "cerco", "severity": 2}
    assert "sitiada" in lq.compose_lore_query(st, "x")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    assert "sitiada" not in lq.compose_lore_query(st, "x")


def test_compose_lore_query_omits_state_when_engine_off(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    monkeypatch.setenv("RPG_CALENDAR", "off")
    q = lq.compose_lore_query(_skall("inverno"), "oi")
    assert q == "Skallgard oi"


def test_compose_lore_query_never_other_location():
    """Oráculo §3.6 (3): cerco de Brekmar (não percebido) não vaza para a query."""
    q = lq.compose_lore_query(_skall("inverno"), "procuro a forja")
    assert "Brekmar" not in q and "sitiada" not in q
    assert "fome" not in q.lower()


def test_compose_lore_query_truncates_input():
    q = lq.compose_lore_query(_skall(None), "a" * 1000)
    assert q.endswith("a" * lq.LORE_QUERY_INPUT_MAX)
    assert "a" * (lq.LORE_QUERY_INPUT_MAX + 1) not in q


def test_compose_lore_query_never_raises():
    assert lq.compose_lore_query({}, "oi") == "oi"
    assert lq.compose_lore_query(None, "oi") == "oi"  # type: ignore[arg-type]
    assert lq.compose_lore_query({"world": {"current_location_id": "nao_existe"}}, "oi") == "oi"


# --- R22: aliases ------------------------------------------------------------------------
def test_slug():
    assert lq.slug("Nova_Arcádia") == "nova_arcadia"
    assert lq.slug("  Pântano da Melancolia ") == "pantano_da_melancolia"


def test_region_lore_tags_every_region_hits_codex():
    """R22: cada uma das 12 regiões tem >= 1 alias presente nas tags de algum .md do Codex."""
    from services import world_pressures as wp
    from services.codex_loader import parse_codex_file

    seen: set[str] = set()
    for root, _dirs, files in os.walk("data/codex"):
        for fname in files:
            if fname.endswith(".md"):
                fm, _ = parse_codex_file(os.path.join(root, fname))
                seen |= {lq.slug(str(t)) for t in fm.get("tags") or []}
    regions = wp.region_ids()
    assert len(regions) == 12
    for rid in regions:
        assert lq.region_lore_tags(rid) & seen, rid


# --- R20/R21: reordenação ----------------------------------------------------------------
def _doc(name: str, tags: list[str], vis: str = "public"):
    return SimpleNamespace(metadata={"tags": tags, "visibility": vis}, page_content=name, text=name)


def test_rerank_by_region_tiers_stable():
    docs = [
        _doc("outra1", ["Brekmar"]),
        _doc("neutro1", ["magica"]),
        _doc("minha1", ["Skallgard"]),
        _doc("neutro2", []),
        _doc("minha2", ["skallgard", "x"]),
        _doc("outra2", ["costa_negra"]),
    ]
    out = [d.page_content for d in lq.rerank_by_region(docs, "skallgard", 6)]
    assert out == ["minha1", "minha2", "neutro1", "neutro2", "outra1", "outra2"]
    assert [d.page_content for d in lq.rerank_by_region(docs, "skallgard", 2)] == [
        "minha1",
        "minha2",
    ]
    assert [d.page_content for d in lq.rerank_by_region(docs, None, 3)] == [
        "outra1",
        "neutro1",
        "minha1",
    ]


def test_rerank_without_tags_is_noop():
    docs = [SimpleNamespace(metadata={}) for _ in range(4)]
    assert lq.rerank_by_region(docs, "skallgard", 3) == docs[:3]


class _FakeIndex:
    def __init__(self, docs):
        self.docs = docs
        self.requested_k = None

    def similarity_search_with_score_by_vector(self, vector, *, k):
        self.requested_k = k
        from langchain_core.documents import Document

        return [
            (Document(page_content=t, metadata=m), 0.1 * i) for i, (t, m) in enumerate(self.docs)
        ][:k]


def _patch_faiss(monkeypatch, docs):
    index = _FakeIndex(docs)
    monkeypatch.setattr(rag, "_has_faiss_index", lambda path: True)
    monkeypatch.setattr(rag, "_embeddings_for_index", lambda path: object())
    monkeypatch.setattr(rag, "FAISS", SimpleNamespace(load_local=lambda *a, **k: index))
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    return index


def test_rerank_never_relaxes_visibility(monkeypatch):
    """R24: chunk hidden com a tag da região atual continua fora."""
    docs = [
        ("fora-1", {"tags": ["brekmar"], "visibility": "public", "id": "a"}),
        ("segredo", {"tags": ["skallgard"], "visibility": "hidden", "id": "b"}),
        ("neutro", {"tags": [], "visibility": "public", "id": "c"}),
        ("minha", {"tags": ["skallgard"], "visibility": "public", "id": "d"}),
    ]
    _patch_faiss(monkeypatch, docs)
    out = rag.query_global_by_vector([1.0, 0.0], "lore", "public", prefer_region="skallgard")
    assert "segredo" not in out
    assert out.split("\n---\n") == ["minha", "neutro", "fora-1"]


def test_query_global_by_vector_without_region_is_unchanged(monkeypatch):
    """R20/R25: sem prefer_region vale a ordem do FAISS, só com LORE_K."""
    docs = [(f"c{i}", {"tags": [], "visibility": "public", "id": str(i)}) for i in range(6)]
    index = _patch_faiss(monkeypatch, docs)
    out = rag.query_global_by_vector([1.0, 0.0], "lore", "public")
    assert out.split("\n---\n") == ["c0", "c1", "c2"] and lq.LORE_K == 3
    assert index.requested_k == 6  # fetch_k inalterado


def test_query_faiss_evidence_untouched():
    import inspect

    sig = inspect.signature(rag.query_faiss_evidence)
    assert "prefer_region" not in sig.parameters


# --- R19: lore fatiada no pack -----------------------------------------------------------
def _lore_budget(tokens: int) -> ContextBudget:
    return ContextBudget(tokens, {"lore": 1.0})


def test_assemble_pack_lore_split_first_chunk_survives():
    """R19: cota para um só chunk => o primeiro entra (antes os dois caíam)."""
    a, b = "A" * 120 + " alfa", "B" * 120 + " beta"
    pack = assemble_pack([], _lore_budget(60), lore_text=f"{a}\n---\n{b}")
    assert a in pack.lore_block and b not in pack.lore_block


def test_assemble_pack_lore_joins_chunks_with_separator():
    pack = assemble_pack(
        [], ContextBudget(3500, {"lore": 0.5}), lore_text="um\n---\ndois\n---\ntres"
    )
    assert pack.lore_block == "um\n---\ndois\n---\ntres"


def test_assemble_pack_lore_ids_keep_prefix():
    pack = assemble_pack([], ContextBudget(3500, {"lore": 0.5}), lore_text="um\n---\ndois")
    ids = [i for i in pack.evidence_ids if str(i).startswith("lore_content_")]
    assert len(ids) == 2 and len(set(ids)) == 2


# --- R18/R23: costuras -------------------------------------------------------------------
def test_custom_readers_signature_untouched(monkeypatch):
    """R23: dublê de query_rag (assinatura antiga) continua funcionando sem prefer_region."""
    import services.context_builder as cb

    calls: list[tuple] = []

    def fake_query_rag(query, index_name="lore", max_visibility="public"):
        calls.append((query, index_name, max_visibility))
        return "lore dublê"

    monkeypatch.setattr(cb, "query_rag", fake_query_rag)
    st = _skall(None)
    pack = cb.build_context_pack(st, query="Skallgard teste", purpose="story")
    assert calls and calls[0][0] == "Skallgard teste"
    assert "lore dublê" in pack.lore_block


def test_default_readers_pass_region_only_when_present(monkeypatch):
    from services.context_sources import EmbeddedContextQuery, _default_readers

    seen: list[dict] = []
    monkeypatch.setattr(
        rag,
        "query_rag",
        lambda q, index_name="lore", max_visibility="public", **kw: seen.append(kw) or "",
    )
    q = EmbeddedContextQuery("x", None, None, None)
    _default_readers(q, game_id=None, npc_id=None)["lore"]()
    _default_readers(q, game_id=None, npc_id=None, prefer_region="skallgard")["lore"]()
    assert seen == [{}, {"prefer_region": "skallgard"}]


def test_storyteller_planner_npc_use_composed_query(monkeypatch):
    """R18: os três chamadores passam por compose_lore_query."""
    import agents.campaign_manager as cm
    import agents.npc as npc_mod
    import agents.storyteller as stt
    from tests.test_ambient_consumers import _Spy, _story_state

    captured: list[tuple[str, str]] = []

    def fake_pack(state, query, purpose, **kw):
        captured.append((purpose, query))
        return SimpleNamespace(
            lore_block="",
            memory_block="",
            world_state_block="",
            evidence_ids=(),
            context_refs=(),
            dropped_ids=(),
        )

    for mod in (stt, cm, npc_mod):
        monkeypatch.setattr(mod, "build_context_pack", fake_pack)
    spy = _Spy()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: spy)
    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: spy)
    st = _story_state(text="procuro a forja")
    try:
        stt.storyteller_node(st)
    except Exception:  # silent-ok: só interessa a query capturada
        pass
    try:
        cm._build_plan(st)
    except Exception:  # silent-ok: só interessa a query capturada
        pass
    by_purpose = dict(captured)
    assert by_purpose["story"].startswith("Skallgard") and by_purpose["story"].endswith("forja")
    assert by_purpose["planning"].startswith("Skallgard")
    assert by_purpose["story"].count("Skallgard") == 1
    assert "region_of" not in by_purpose["story"]
    assert hasattr(npc_mod, "compose_lore_query")
