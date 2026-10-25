"""SPEC-309 Etapa 3 (R7, R8, R10, R11): o dia percebido vira memoria canonica (texto de template)."""

from __future__ import annotations

import pytest

from agents import world_simulator as wsim
from services import perceived_world as pw
from services import world_engine as we
from services import world_perception as wperc
from services.world_director import digest_item
from tests.test_spec302_perception import _CountingLLM, _item, _rest_state, _state, _stub_tick


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _run(monkeypatch, items):
    from main import app

    monkeypatch.setattr(we, "advance_days", _stub_tick(1, items[0] if items else None))
    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _CountingLLM())
    return app.invoke(_rest_state("Noite"))


def _engine_facts(out):
    return [
        f
        for f in out.get("memory_facts") or []
        if str(f.get("source_id", "")).startswith("engine_policy:")
    ]


def test_perceived_items_become_canonical_facts():
    """R7: texto = world_perception.render."""
    st = _state()
    items = [_item("fome.sinal.preco"), _item("guerra.sinal.patrulha")]
    assert pw.day_memory_facts(st, items) == [wperc.render(st, i) for i in items]


def test_no_items_no_facts():
    assert pw.day_memory_facts(_state(), []) == []


def test_cap_day_facts_and_dedupe():
    st = _state()
    items = [_item("fome.sinal.celeiro", params={"local": f"x{i}"}) for i in range(10)]
    assert len(pw.day_memory_facts(st, items)) <= pw.DAY_FACTS_MAX
    same = [_item("fome.sinal.preco"), _item("fome.sinal.preco")]
    assert len(pw.day_memory_facts(st, same)) == 1


def test_archivist_persists_as_canonical_event_engine_policy(monkeypatch):
    """R8 + R10: grava canonical_event engine_policy; a allowlist nao sobrevive ao arquivista."""
    item = _item("fome.sinal.preco", region="nova_arcadia", loc="nova_arcadia")
    out = _run(monkeypatch, [item])
    news = [n["text"] for n in out["world"].get("news", []) if n["source"] == "world_engine"]
    facts = _engine_facts(out)
    assert facts, "o dia percebido deve virar memoria canonica"
    assert all(f["provenance"] == "canonical_event" for f in facts)
    assert {f["text"] for f in facts} <= set(news)
    assert not out.get("memory_canonical_facts")


def test_llm_prose_not_stored_as_canonical(monkeypatch):
    """R11."""
    item = _item("fome.sinal.preco", region="nova_arcadia", loc="nova_arcadia")
    out = _run(monkeypatch, [item])
    assert not any(
        "Marechal Inventado" in str(f.get("text")) for f in out.get("memory_facts") or []
    )


def test_no_facts_no_archive_trigger_when_nothing_perceived(monkeypatch):
    from main import app

    monkeypatch.setattr(we, "advance_days", _stub_tick(0, None))
    out = app.invoke(_rest_state("Manhã"))
    assert _engine_facts(out) == []


def test_facts_written_even_when_encounter_took_world_note(monkeypatch):
    """P8: com `world_note` ocupado o texto de template ainda e gravado (R7 independe da LLM)."""
    from agents import storyteller

    monkeypatch.setattr(storyteller, "_narrate_world", lambda *a, **k: "")
    item = _item("fome.sinal.preco", region="nova_arcadia", loc="nova_arcadia")
    out = _run(monkeypatch, [item])
    assert _engine_facts(out)


def test_archivist_clears_allowlist_without_canonical_only():
    """R10: 2a execucao nao regrava o fato com outro source_turn."""
    from agents.archivist import archive_node

    st = _rest_state("Manhã")
    st["memory_canonical_facts"] = ["Fato do motor de teste."]
    st["memory_fact_policy"] = None
    st["archive_due"] = True
    first = archive_node(st)
    assert first.get("memory_canonical_facts") == []
    assert any(f["text"] == "Fato do motor de teste." for f in first["memory_facts"])
    st2 = {**st, **first, "world": {**st["world"], "turn_count": st["world"]["turn_count"] + 3}}
    second = archive_node(st2)
    count = [
        f
        for f in second.get("memory_facts", first["memory_facts"])
        if f["text"] == "Fato do motor de teste."
    ]
    assert len(count) == 1


def test_crisis_opened_and_perceived_same_turn_one_fact():
    """R9: tipo do motor nao duplica por evento; so o digest (R7) grava."""
    from agents.archivist import _event_memory_records
    from tests.spec309_helpers import world_state_two_regions

    state = world_state_two_regions(perceive_siege=True)
    assert _event_memory_records(state["event_log"], state) == []
    item = digest_item(
        "g", 5, "crise", "skallgard", "skallgard", "fome.sinal.preco", {"local": "skallgard"}
    )
    assert len(pw.day_memory_facts(_state("skallgard"), [item])) == 1
