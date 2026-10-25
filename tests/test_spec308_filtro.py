"""SPEC-308: regra de ouro para os eventos do motor de mundo."""

from __future__ import annotations

import pytest

from services import world_director as wd
from services import world_perception as wperc
from services.context_builder import build_context_pack, collect_dynamic_facts

HERE = "nova_arcadia"
FAR_A, FAR_B = "skallgard", "sk_fortaleza_vorr"


def _state(loc: str = HERE, day: int = 5, ledger=None, **extra) -> dict:
    return {
        "game_id": "g-308",
        "event_log": [],
        "world_projection": {},
        "world": {
            "current_location_id": loc,
            "current_location": loc,
            "world_clock": {"day": day, "period": "Manhã"},
            "turn_count": 10,
        },
        "world_sim": {"perceived_ids": list(ledger or [])},
        **extra,
    }


def _ev(etype="route_blocked", target=FAR_A, eid="e1", source="engine", turn=3, **payload) -> dict:
    return {
        "event_id": eid,
        "type": etype,
        "actor_id": "engine",
        "target_id": target,
        "turn": turn,
        "source": source,
        "payload": {"other_location_id": FAR_B, **payload},
    }


def test_non_engine_event_always_perceived():
    ev = _ev(source="storyteller")
    assert wperc.event_perceived(_state(), ev)
    assert wperc.event_perceived(_state(), {"type": "npc_killed", "payload": {}})


def test_engine_event_hidden_until_ledger():
    ev = _ev()
    assert not wperc.event_perceived(_state(), ev)
    assert wperc.event_perceived(_state(ledger=["e1"]), ev)


def test_engine_event_perceived_by_ledger_event_id():
    ev = _ev(eid="evt-xyz")
    assert wperc.event_perceived(_state(ledger=["outro", "evt-xyz"]), ev)
    assert not wperc.event_perceived(_state(ledger=["outro"]), ev)


def test_engine_event_same_place_same_day_is_witness():
    ev = _ev(target=HERE, day=5)
    assert wperc.event_perceived(_state(loc=HERE, day=5), ev)
    assert not wperc.event_perceived(_state(loc=HERE, day=6), ev)  # outro dia


def test_engine_event_other_region_hidden():
    ev = _ev(target=FAR_A, day=5)
    assert not wperc.event_perceived(_state(loc=HERE, day=5), ev)


def test_derived_event_uses_cause():
    derived = _ev("location_control_changed", eid="d1", source="rule_engine", cause_event_id="e1")
    assert not wperc.event_perceived(_state(), derived)
    assert wperc.event_perceived(_state(ledger=["e1"]), derived)
    # derivado de evento que NAO e do motor nao e filtrado
    assert wperc.event_perceived(_state(), _ev(eid="d2", source="rule_engine"))


def test_known_sources_from_304_count():
    st = _state(npc_beliefs={"npc_a": {"source_event_id": "e1", "known_events": ["e9"]}})
    assert wperc.event_perceived(st, _ev(eid="e1"))
    assert wperc.event_perceived(st, _ev(eid="e9"))
    assert not wperc.event_perceived(st, _ev(eid="e2"))


def test_digest_items_carry_event_ids():
    item = wd.digest_item("g", 1, "crise", "r", "l", "t", event_ids=["a", "b"])
    assert item["event_ids"] == ["a", "b"]
    assert "event_ids" not in wd.digest_item("g", 1, "sinal", "r", "l", "t")


def test_digest_from_director_links_events(monkeypatch):
    from services import world_engine as we
    from tests.spec302_helpers import fresh_sim, set_pressure

    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    sim = fresh_sim(1)
    set_pressure(sim, "nova_arcadia", "guerra", 85)
    events, digest = [], []
    for day in range(2, 40):
        _sim, ev, dg = wd.step_crises(
            sim,
            day,
            {},
            we.day_rng("g", day, "director"),
            game_id="g",
            factions=[],
            faction_region=we.faction_region_id,
        )
        events += ev
        digest += dg
    ids = {e["event_id"] for e in events}
    linked = [d for d in digest if d["kind"] in ("aviso", "crise", "escala", "fim")]
    assert linked
    for d in linked:
        assert d["event_ids"] and set(d["event_ids"]) <= ids


def _tick(ledger_old, event_ids):
    class Tick:
        sim_key = "world_sim"
        days_ticked = 1
        world_sim = {
            "perceived_ids": list(ledger_old),
            "pending_digest": [
                {
                    "item_id": "i1",
                    "day": 5,
                    "kind": "crise",
                    "region_id": "nova_arcadia",
                    "location_id": HERE,
                    "template_id": "guerra.crise.inicio",
                    "params": {"local": HERE},
                    "subject_id": "s1",
                    "event_ids": event_ids,
                }
            ],
        }

    return Tick


def test_ledger_records_event_ids_on_perception():
    from agents import storyteller

    tick = _tick([], ["e1", "e2"])
    storyteller._perceive_world(_state(), _state()["world"], [], {}, tick)
    assert {"s1", "e1", "e2"} <= set(tick.world_sim["perceived_ids"])


def test_ledger_cap_400_fifo():
    from agents import storyteller

    tick = _tick([f"old{i}" for i in range(399)], ["n1", "n2", "n3"])
    storyteller._perceive_world(_state(), _state()["world"], [], {}, tick)
    ledger = tick.world_sim["perceived_ids"]
    assert len(ledger) == 400
    assert ledger[-1] == "n3" and "old0" not in ledger


def _remote_siege_state(ledger=None) -> dict:
    return _state(ledger=ledger, event_log=[_ev("route_blocked", FAR_A, "siege1", day=5)])


@pytest.mark.parametrize("npc_world", ["off", "on"])
@pytest.mark.parametrize("purpose", ["story", "planning"])
def test_remote_siege_not_in_story_or_planning_context(monkeypatch, npc_world, purpose):
    monkeypatch.setenv("RPG_NPC_WORLD", npc_world)
    marker = "BLOQUEADA"
    hidden = collect_dynamic_facts(
        _remote_siege_state(), purpose=purpose, query="", current_loc=HERE, scene_entities=[]
    )
    assert not any(marker in f.text for f in hidden)
    pack = build_context_pack(_remote_siege_state(), "q", purpose)
    assert marker not in pack.world_state_block
    seen = collect_dynamic_facts(
        _remote_siege_state(["siege1"]),
        purpose=purpose,
        query="",
        current_loc=HERE,
        scene_entities=[],
    )
    assert any(marker in f.text for f in seen)


def test_rpg_npc_world_off_still_filters(monkeypatch):
    monkeypatch.setenv("RPG_NPC_WORLD", "off")
    facts = collect_dynamic_facts(
        _remote_siege_state(), purpose="story", query="", current_loc=HERE, scene_entities=[]
    )
    assert not any("BLOQUEADA" in f.text for f in facts)


def test_chronicle_milestone_only_after_perception():
    from services import chronicle

    ev = _ev("location_control_changed", FAR_A, "c1", turn=2, day=5, new_controller_id="x")
    assert chronicle.perceived_milestones(_state(event_log=[ev])) is None
    st2 = _state(ledger=["c1"], event_log=[ev])
    out = chronicle.perceived_milestones(st2)
    assert out and any(e.get("event_id") == "c1" for ch in out for e in ch["entries"])
    assert chronicle.perceived_milestones({**st2, "chronicle": out}) is None  # idempotente


def test_memory_fact_only_after_perception():
    from agents.archivist import _event_memory_records

    ev = _ev("route_blocked", FAR_A, "m1", day=5)
    assert _event_memory_records([ev], _state()) == []
    assert len(_event_memory_records([ev], _state(ledger=["m1"]))) == 1


def test_companion_fate_decided_by_belief(monkeypatch):
    ev = _ev("companion_fate", "comp_1", "cf1", fate="morto")
    ev["payload"].pop("other_location_id")
    for mode in ("off", "on"):
        monkeypatch.setenv("RPG_NPC_WORLD", mode)
        assert not wperc.event_perceived(_state(), ev)
        st = _state(npc_beliefs={"comp_1": {"source_event_id": "cf1"}})
        assert wperc.event_perceived(st, ev)
