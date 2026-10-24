"""SPEC-305 Etapas 4-5: conclusao, alivio (contra-jogo), prazo e falha."""

from __future__ import annotations

import copy

from services import event_processor as ep
from services import quest_log as ql
from services import world_director as wd
from services import world_engine as we
from services import world_pressures as wp
from services import world_quests as wq
from tests.spec302_helpers import quiet, set_pressure, tick
from tests.spec305_helpers import GID, add_crisis, base_state, crisis_item


def _offered(state: dict, day: int = 17, item: dict | None = None) -> dict:
    quests, created = wq.offer_from_perceived(state, [item or crisis_item()], day)
    assert created
    state["quests"] = quests
    return created[0]


def test_kind_vocab_counts_as_evidence():
    state = base_state()
    add_crisis(state)
    q = _offered(state)
    qs = ql.sync_location_progress(state["quests"], "brekmar", turn=18)
    qs, ready = ql.sync_action_progress(qs, "brekmar", "Trato os doentes com ervas", turn=19)
    assert ready == []
    qs, ready = ql.sync_action_progress(qs, "brekmar", "Queimo as roupas e isolo a rua", turn=20)
    assert ready == [q["id"]]


def test_generic_investigation_regex_still_works_for_common_quests():
    common = {
        "id": "c1",
        "title": "Achar o medalhão",
        "description": "",
        "status": "active",
        "location_id": "brekmar",
        "created_turn": 1,
        "progress_log": [{"kind": "location_reached", "turn": 2}],
    }
    qs, ready = ql.sync_action_progress([common], "brekmar", "Investigo a missão no cais", turn=3)
    qs, ready = ql.sync_action_progress(
        qs, "brekmar", "Procuro a pista com o estalajadeiro", turn=4
    )
    assert ready == ["c1"]


def test_combat_won_counts_once_for_siege():
    state = base_state()
    add_crisis(state, "guerra", "brekmar", faction_id="legiao_ferro")
    _offered(state, item=crisis_item("guerra"))
    qs = ql.sync_location_progress(state["quests"], "brekmar", turn=18)
    qs = ql.sync_combat_progress(qs, "brekmar", turn=19)
    qs = ql.sync_combat_progress(qs, "brekmar", turn=19)  # mesmo combate: idempotente
    assert [r["kind"] for r in qs[0]["progress_log"]].count("combat_won") == 1
    ok, _why = ql.has_completion_proof(qs[0], {"world": {"turn_count": 20}})
    assert ok
    # tipo que nao conta combate (praga) ignora
    pr = base_state()
    add_crisis(pr)
    _offered(pr)
    prq = ql.sync_combat_progress(
        ql.sync_location_progress(pr["quests"], "brekmar", turn=18), "brekmar", turn=19
    )
    assert "combat_won" not in [r["kind"] for r in prq[0]["progress_log"]]


def test_completion_requires_arrival_before_deadline():
    state = base_state()
    add_crisis(state)
    _offered(state)
    ok, why = ql.has_completion_proof(state["quests"][0], {"world": {"turn_count": 30}})
    assert not ok and "chegada" in why


def _complete(state: dict, qid: str) -> dict:
    ev = {
        "type": "quest_completed",
        "target_id": qid,
        "payload": {"quest_id": qid},
        "source": "engine",
    }
    return ep.process_pending_events({**state, "pending_world_events": [ev]})


def test_relief_event_derived_on_completion_and_read_by_pressures():
    state = base_state()
    add_crisis(state)
    q = _offered(state)
    out = _complete(state, q["id"])
    rel = [e for e in out["event_log"] if e["type"] == "world_quest_relief"][0]
    deltas = wp.event_deltas([rel])
    assert deltas["brekmar"]["praga"] == -25


def test_relieved_crisis_does_not_escalate():
    """Oraculo: alivio em e-2 -> sem escalada em e; sem alivio -> escala."""
    cfg = quiet()
    k = wp.constants(cfg)
    results = {}
    for relieved in (True, False):
        sim = we._new_sim(GID, 17, [], "on")
        sim["calm_until_day"] = 0
        sim["crises"].append(
            {
                "crisis_id": "c",
                "kind": "praga",
                "region_id": "brekmar",
                "location_id": "brekmar",
                "loc_state": "praga",
                "faction_id": "",
                "warned_day": 14,
                "start_day": 17,
                "escalation_day": 23,
                "severity": 1,
                "end_day": None,
                "resolution": "",
            }
        )
        set_pressure(sim, "brekmar", "praga", int(k["CRISE"]) + 10)
        if relieved:
            wd.relieve(sim, "c", 21)  # e-2
        proj = {"location_states": {"brekmar": {"state": "praga"}}}
        import random

        wd.step_crises(sim, 23, proj, random.Random(1), game_id=GID, cfg=cfg)
        results[relieved] = sim["crises"][0]["severity"] if sim["crises"] else None
    assert results[True] == 1 and results[False] == 2


def test_relieved_crisis_ends_with_intervencao():
    import random

    cfg = quiet()
    sim = we._new_sim(GID, 17, [], "on")
    sim["calm_until_day"] = 0
    sim["crises"].append(
        {
            "crisis_id": "c",
            "kind": "praga",
            "region_id": "brekmar",
            "location_id": "brekmar",
            "loc_state": "praga",
            "faction_id": "",
            "warned_day": 10,
            "start_day": 12,
            "escalation_day": 18,
            "severity": 1,
            "end_day": None,
            "resolution": "",
        }
    )
    set_pressure(sim, "brekmar", "praga", 10)
    wd.relieve(sim, "c", 16)
    wd.step_crises(sim, 17, {}, random.Random(1), game_id=GID, cfg=cfg)
    assert sim["crises"][0]["resolution"] == "intervencao"


def test_engine_tick_reads_relief_event_from_log():
    state = base_state(day=17)
    state["world_sim"] = we._new_sim(GID, 17, [], "on")
    state["world_sim"]["calm_until_day"] = 0
    add_crisis(state, "praga", "brekmar")
    state["world_sim"]["last_event_seq"] = 0
    state["event_log"] = [
        {
            "event_id": "r1",
            "type": "world_quest_relief",
            "target_id": "brekmar",
            "payload": {"world_source_id": "crise-1", "day": 17, "pressure": "praga", "delta": -25},
        }
    ]
    tick(state, 17, 18)
    assert state["world_sim"]["crises"][0].get("relieved_day") == 17


def test_reabrir_rota_emits_route_cleared_engine():
    q = {
        "id": "qr",
        "title": "Reabrir",
        "status": "active",
        "world_kind": "reabrir_rota",
        "world_source_id": "route:nova_arcadia|brekmar:ev",
        "location_id": "nova_arcadia",
        "other_location_id": "brekmar",
        "region_id": "nova_arcadia",
        "progress_log": [],
    }
    proj = {"blocked_routes": [{"a": "nova_arcadia", "b": "brekmar", "blocked_by_event": "ev"}]}
    out = _complete(
        {
            "game_id": GID,
            "world": {"turn_count": 4, "world_clock": {"day": 9}},
            "world_projection": proj,
            "event_log": [],
            "chronicle": [],
            "quests": [q],
        },
        "qr",
    )
    cleared = [e for e in out["event_log"] if e["type"] == "route_cleared"]
    assert cleared and cleared[0]["source"] == "engine"
    assert out["world_projection"]["blocked_routes"] == []


def test_liberation_raises_reoccupy_chance_and_failure_consolidates():
    import random

    def run(row_extra: dict) -> int:
        sim = we._new_sim(GID, 20, [], "on")
        sim["war_calm_days"] = {"nova_arcadia": 99}
        proj = {
            "location_states": {
                "nova_arcadia": {"state": "ocupado", "since_day": 5, "faction_id": "x", **row_extra}
            }
        }
        hits = 0
        for seed in range(400):
            ev, _ = wd.recovery_step(sim, 20, proj, random.Random(seed), game_id=GID, factions=[])
            hits += any(e["payload"].get("previous") == "ocupado" for e in ev)
            sim["war_calm_days"] = {"nova_arcadia": 99}
        return hits

    base, lib = run({}), run({"liberation_day": 18})
    assert lib > base * 2
    assert run({"consolidated_until_day": 40}) == 0


def test_ascension_setback_clamped():
    q = {
        "id": "qa",
        "title": "Frear",
        "status": "active",
        "world_kind": "frear_ascensao",
        "world_source_id": "c-asc",
        "location_id": "skallgard",
        "region_id": "skallgard",
        "progress_log": [],
    }
    state = {
        "game_id": GID,
        "world": {"turn_count": 4, "world_clock": {"day": 9}},
        "world_projection": {},
        "event_log": [],
        "chronicle": [],
        "quests": [q],
        "factions": [{"id": "clas_combate", "progress": 10}],
        "world_sim": {"crises": [{"crisis_id": "c-asc", "faction_id": "clas_combate"}]},
    }
    out = _complete(state, "qa")
    assert out["factions"][0]["progress"] == 0


# --- prazo e falha ---------------------------------------------------------


def _with_quest(day: int = 17, esc: int = 23) -> dict:
    state = base_state(day=day)
    add_crisis(state, escalation=esc)
    _offered(state, day=day)
    return state


def test_fails_on_deadline_tick_not_before():
    state = _with_quest()
    _q, ev = wq.sync_deadlines(state, 22)
    assert ev == []
    _q, ev = wq.sync_deadlines(state, 23)
    assert [e["type"] for e in ev] == ["quest_failed"] and ev[0]["source"] == "engine"
    assert ev[0]["payload"]["reason"] == "prazo"
    # idempotente: ja enfileirada, nao repete
    state["pending_world_events"] = ev
    assert wq.sync_deadlines(state, 23)[1] == []


def test_multi_day_travel_arriving_on_deadline_fails():
    state = _with_quest()
    state["world"]["world_clock"]["day"] = 25
    assert wq.sync_deadlines(state, 25)[1]


def test_source_ended_alone_expires_without_failure():
    state = _with_quest()
    state["world_sim"]["crises"][0].update(end_day=20, resolution="recuperou")
    qs, ev = wq.sync_deadlines(state, 22)
    assert qs[0]["status"] == "active" and ev == []  # ainda nao percebeu o fim
    qs, ev = wq.sync_deadlines(state, 23)
    assert qs[0]["status"] == "expired" and qs[0]["fail_reason"] == "superada" and ev == []


def test_perceived_end_expires_immediately():
    state = _with_quest()
    state["world_sim"]["crises"][0].update(end_day=20, resolution="recuperou")
    fim = crisis_item(tpl="crise.fim", item_kind="fim", day=20)
    qs, ev = wq.sync_deadlines(state, 20, perceived=[fim])
    assert qs[0]["status"] == "expired" and ev == []


def test_escalated_crisis_fails_at_deadline_with_neutral_text():
    state = _with_quest()
    state["world_sim"]["crises"][0].update(end_day=23, resolution="escalou")
    _qs, ev = wq.sync_deadlines(state, 23)
    assert ev
    out = ep.process_pending_events({**state, "pending_world_events": ev})
    q = out["quests"][0]
    assert q["status"] == "failed"
    blob = (q["title"] + q["description"]).lower()
    for word in ("caiu", "morreu", "morto", "ocupad", "ruína", "ruina"):
        assert word not in blob


def test_fail_causes_route_fome_once():
    ev = {
        "type": "quest_failed",
        "payload": {
            "world_kind": "reabrir_rota",
            "location_id": "nova_arcadia",
            "other_location_id": "brekmar",
        },
        "target_id": "q",
    }
    d = wp.event_deltas([ev])
    assert d["nova_arcadia"]["fome"] == 6 and d["brekmar"]["fome"] == 6


def test_occupation_consolidates_on_failure():
    proj = {"location_states": {"nova_arcadia": {"state": "ocupado", "since_day": 5}}}
    ev = {
        "type": "quest_failed",
        "target_id": "q",
        "event_id": "e1",
        "turn": 3,
        "payload": {"world_kind": "libertar_ocupado", "location_id": "nova_arcadia", "day": 15},
    }
    out = ep.apply_event(ev, copy.deepcopy(proj))
    assert out["location_states"]["nova_arcadia"]["consolidated_until_day"] == 45


def test_unheard_invariant_and_early_fail_detected():
    from playtest import invariants as inv

    state = _with_quest()
    state["quests"][0]["heard_via"] = {"channel": "rumor", "event_id": "nunca-ouvi", "day": 17}
    ids = {v.check_id for v in inv.check_world_quests(state, None, 3)}
    assert "quest.world_unheard" in ids
    state["quests"][0].update(status="failed", fail_reason="prazo", resolved_day=19)
    ids = {v.check_id for v in inv.check_world_quests(state, None, 3)}
    assert "quest.failed_before_deadline" in ids
    prev = {"quests": [{**state["quests"][0], "deadline_day": 99}]}
    ids = {v.check_id for v in inv.check_world_quests(state, prev, 3)}
    assert "quest.deadline_shortened" in ids


class _FakePeril:
    """Contrato minimo da SPEC-304 (`npc_world.active_perils`) injetado para o teste."""

    def __init__(self, resolution: str = "", deadline: int = 20):
        self.row = {
            "peril_id": "p1",
            "npc_id": "npc_x",
            "held_at_location_id": "brekmar",
            "deadline_day": deadline,
            "resolution": resolution,
            "region_id": "brekmar",
        }

    def active_perils(self, state):
        return [self.row]


def test_resgate_with_fake_304_contract(monkeypatch):
    import sys
    import types

    fake = _FakePeril()
    mod = types.ModuleType("services.npc_world")
    mod.active_perils = fake.active_perils
    monkeypatch.setitem(sys.modules, "services.npc_world", mod)
    import services

    monkeypatch.setattr(services, "npc_world", mod, raising=False)
    state = base_state(loc="brekmar")
    seeds = {s.kind: s for s in wq.candidates(state, 17)}
    assert seeds["resgate"].deadline_day == 20
    state["quests"] = [
        {
            "id": "qp",
            "status": "active",
            "world_kind": "resgate",
            "world_source_id": "p1",
            "location_id": "brekmar",
            "deadline_day": 20,
            "title": "r",
            "progress_log": [],
        }
    ]
    fake.row["resolution"] = "intervencao"
    evs = wq.engine_completions(state)
    assert evs and evs[0]["type"] == "quest_completed" and evs[0]["source"] == "engine"
    fake.row["resolution"] = "morto"  # qualquer destino != intervencao falha, sem nomeá-lo
    _qs, ev = wq.sync_deadlines(state, 18)
    assert ev and ev[0]["payload"]["reason"] == "prazo"
    assert "morto" not in str(ev[0]["payload"])
