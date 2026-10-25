"""SPEC-308 (revisao Sol): oraculo de vazamento com projection REAL nos 4 packs + API."""

from __future__ import annotations

import pytest

from services import graph_resolver as gr
from services import world_director as wd
from services import world_perception as wperc
from services.context_builder import build_context_pack
from services.event_processor import process_pending_events

FAR = "sk_fortaleza_vorr"
A, B = "clas_combate", "tribos_devoradores_sol"


def _name(i):
    return (gr.get_entity(i) or {}).get("name", i)


def _events():
    return [
        wd._ev(
            "g",
            5,
            "faction_relation_changed",
            A,
            {"other_faction_id": B, "relation": "enemy_of"},
            B,
        ),
        wd._ev(
            "g", 5, "location_control_changed", FAR, {"new_controller_id": B, "crisis_id": "c1"}
        ),
        wd._ev("g", 5, "route_blocked", "skallgard", {"other_location_id": FAR, "crisis_id": "c1"}),
    ]


def _state(ledger=None) -> dict:
    state = {
        "game_id": "g",
        "event_log": [],
        "world_projection": {},
        "pending_world_events": _events(),
        "world": {
            "current_location_id": "nova_arcadia",
            "current_location": "Nova Arcadia",
            "world_clock": {"day": 5, "period": "Manhã"},
            "turn_count": 10,
            "visited": ["nova_arcadia", FAR],
        },
        "world_sim": {"perceived_ids": list(ledger or [])},
        "chronicle": [],
    }
    state.update(process_pending_events(state))
    state["world"]["world_clock"]["day"] = 7
    state["world"]["turn_count"] = 14
    return state


@pytest.mark.parametrize("npc_world", ["off", "on"])
@pytest.mark.parametrize("purpose", ["story", "npc", "combat_narration", "planning"])
def test_remote_world_event_does_not_leak_through_projection(monkeypatch, npc_world, purpose):
    monkeypatch.setenv("RPG_NPC_WORLD", npc_world)
    state = _state()
    assert len(state["event_log"]) >= 3  # aplicados de verdade (projection real)
    rel = f"{_name(A)} —enemy_of→ {_name(B)}"
    ctl = f"{_name(B)} —controls→ {_name(FAR)}"
    terms = [rel, ctl, "BLOQUEADA"]
    txt = build_context_pack(state, "o que acontece no mundo", purpose).world_state_block
    assert [t for t in terms if t in txt] == []
    # depois da percepcao dos eventos, o fato aparece
    ids = [e["event_id"] for e in state["event_log"]]
    seen = build_context_pack(
        {**state, "world_sim": {"perceived_ids": ids}}, "o que acontece no mundo", purpose
    ).world_state_block
    assert ctl in seen and rel in seen


def test_api_blocks_hide_unperceived_engine_facts():
    import api
    from services import dossiers
    from services.map_view import build_map_view

    state = _state()
    w = _api_world(state)
    assert FAR not in w["controlled"] or w["controlled"][FAR] != _name(B)
    assert w["map_overlays"]["control_changes"] == []
    assert w["blocked_routes"] == []
    nodes = {
        n["id"] if "id" in n else n.get("location_id"): n for n in build_map_view(state)["nodes"]
    }
    assert not nodes.get(FAR, {}).get("contested")
    assert dossiers._events_about(state, FAR) == []

    ids = [e["event_id"] for e in state["event_log"]]
    state2 = {**state, "world_sim": {"perceived_ids": ids}}
    w2 = _api_world(state2)
    assert w2["controlled"][FAR] == _name(B)
    assert w2["map_overlays"]["control_changes"]
    assert w2["blocked_routes"]
    assert dossiers._events_about(state2, FAR)
    assert api  # import guard


def _api_world(state):
    import api

    return api._world_block(
        state["world"],
        state["world_projection"],
        state["event_log"],
        {},
        state.get("world_sim"),
        state=state,
    )


def test_cascade_inherits_cause_only_from_world_types(monkeypatch):
    from services import event_processor as ep

    def fake_rules(event, working, depth=0):
        return [
            {
                "event_id": "dv-" + event["event_id"],
                "type": "faction_relation_changed",
                "source": "rule_engine",
                "actor_id": "x",
                "target_id": A,
                "payload": {"other_faction_id": B, "relation": "enemy_of"},
            }
        ]

    monkeypatch.setattr(ep.rule_engine, "run_rules", fake_rules)
    base = {
        "game_id": "g",
        "event_log": [],
        "world_projection": {},
        "world": {
            "current_location_id": "nova_arcadia",
            "turn_count": 3,
            "world_clock": {"day": 1},
        },
    }
    ctl = wd._ev("g", 1, "location_control_changed", FAR, {"new_controller_id": B})
    out = ep.process_pending_events({**base, "pending_world_events": [ctl]})
    dv = next(e for e in out["event_log"] if e["event_id"].startswith("dv-"))
    assert dv["payload"].get("cause_event_id") == ctl["event_id"]
    # evento do motor que NAO e do motor de mundo (quest) nao esconde a consequencia
    qc = {
        "event_id": "qq1",
        "type": "quest_completed",
        "source": "engine",
        "actor_id": "player",
        "target_id": "q",
        "payload": {},
    }
    out = ep.process_pending_events({**base, "pending_world_events": [qc]})
    dvs = [e for e in out.get("event_log", []) if e["event_id"].startswith("dv-")]
    assert all("cause_event_id" not in e["payload"] for e in dvs)


def test_route_cleared_by_hero_is_witnessed_anywhere():
    ev = {
        "event_id": "r1",
        "type": "route_cleared",
        "source": "engine",
        "actor_id": "player",
        "target_id": "skallgard",
        "turn": 1,
        "payload": {"other_location_id": FAR},
    }
    st = {"world": {"current_location_id": "nova_arcadia", "turn_count": 9}, "world_sim": {}}
    assert wperc.event_perceived(st, ev)
    assert not wperc.event_perceived(st, {**ev, "actor_id": "engine"})


def test_recovery_reoccupy_digest_links_state_event():
    from services import world_engine as we
    from tests.spec302_helpers import fresh_sim

    proj = {
        "location_states": {
            "na_anel_lama": {
                "state": "ocupado",
                "since_day": 3,
                "faction_id": "legiao_ferro",
                "prev_controller": "mao_sombria",
            }
        }
    }
    facs = [{"id": "legiao_ferro", "defeated": True}, {"id": "mao_sombria"}]
    ev, dg = wd.recovery_step(
        fresh_sim(), 10, proj, we.day_rng("g", 10, "r"), game_id="g", factions=facs
    )
    assert [e["type"] for e in ev] == ["location_state_changed", "location_control_changed"]
    assert dg[0]["subject_id"] == ev[0]["event_id"]
    assert dg[0]["event_ids"] == [ev[0]["event_id"], ev[1]["event_id"]]
