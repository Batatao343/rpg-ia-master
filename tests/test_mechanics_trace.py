"""SPEC-251: trace mecânico do conflito (rolagens, dano, morte, reações, fuga)."""
import json
import random

import pytest
from langchain_core.messages import HumanMessage

import agents.combat as combat
import gamedata
from observability import logging_setup
from services import audit_trace, chase, death_flow, mechanics_trace as mt, reactions
from services.conflict_damage import resolve_damage_and_wounds
from services.conflict_orchestrator import ensure_combat_sheet
from services.conflict_resolution import resolve_attack, roll_initiative_by_side

from tests.test_aliados_combate import _enemy, _player, _world

NAME = "Fulano Sentinela251"


def _actor(ident, *, player=False, name=NAME):
    a = ensure_combat_sheet({"id": ident, "name": name}, is_player=player)
    return a


def test_attack_records_dice_and_result():
    hero, foe = _actor("player", player=True), _actor("mon_cao_rebite")
    with mt.scope():
        atk = resolve_attack(hero, foe, virtude_key="forca", rng=random.Random(3))
        dmg = resolve_damage_and_wounds(foe, damage_base=4, damage_type="cortante",
                                        rng=random.Random(3))
        snap = mt.snapshot()
    a, d = snap["steps"][0], snap["steps"][1]
    assert a["kind"] == "attack" and a["actor_ref"] == "player" and a["target_ref"] == "mon_cao_rebite"
    assert a["dice"] == atk["dice_rolled"] and a["kept"] == atk["dice_kept"]
    assert a["dc_or_defense"] == atk["esquiva_alvo"] and a["result"] == atk["resultado"]
    assert d["kind"] == "damage" and d["amount"] == dmg["dano_final"]


def test_death_flow_stages_recorded():
    victim = _actor("player", player=True)
    with mt.scope():
        death_flow.trigger_last_stand(victim)
        death_flow.enter_terminal_state(victim)
        res = death_flow.attempt_stabilization(victim, helper=None)
        steps = mt.snapshot()["steps"]
        agg = mt.summary()
    assert res["dead"] is True
    assert [s["result"] for s in steps] == ["last_stand", "terminal", "dead"]
    assert agg["death_stage_reached"] == "dead"


def test_flee_reaction_and_initiative_recorded():
    with mt.scope():
        roll_initiative_by_side({"hero": [_actor("player", player=True)],
                                 "enemy": [_actor("mon_x")]}, rng=random.Random(1))
        c = chase.start_chase({"positions": {}}, "player", [_actor("mon_x")]) \
            if False else {"trilha": "pressionado"}
        chase.resolve_chase_round(c, condutor_virtude=2, rng=random.Random(2))
        reactions.trigger_opportunity_attack(
            {"positions": {"player": {"engaged_with": ["mon_x"]}, "mon_x": {}}}, "player")
        kinds = [s["kind"] for s in mt.snapshot()["steps"]]
        assert mt.summary()["rounds"] == 1 and mt.summary()["reactions"] == 1
    assert kinds == ["initiative", "flee", "reaction"]


def test_trace_capped():
    with mt.scope():
        for _ in range(mt.MAX_STEPS + 10):
            mt.record_step("reaction", actor="player", result="offered")
        snap = mt.snapshot()
        assert len(snap["steps"]) == mt.MAX_STEPS and snap["truncated"] == 10
        assert mt.summary()["reactions"] == mt.MAX_STEPS + 10


def test_noop_without_scope():
    mt.record_step("attack", actor="player")
    assert mt.snapshot() is None


def test_trace_parity_same_seed(monkeypatch):
    def run(trace_on):
        if not trace_on:
            monkeypatch.setattr(mt, "record_step", lambda *a, **k: None)
        random.seed(11)
        state = {"game_id": "p", "messages": [HumanMessage(content="Ataco o Goblin 1")],
                 "player": _player(), "enemies": [_enemy(hp=40)], "combat": {"active": True},
                 "world": _world(), "party": [], "npcs": {}}
        out = combat.combat_node(state)
        monkeypatch.undo()
        return json.dumps({k: out.get(k) for k in ("player", "enemies", "combat")},
                          sort_keys=True, default=str), random.random()
    assert run(True) == run(False)


def test_combat_node_emits_logs_and_audit_trace(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})
    random.seed(5)
    state = {"game_id": "p", "messages": [HumanMessage(content="Ataco o Goblin 1")],
             "player": _player(), "enemies": [_enemy(hp=40)], "combat": {"active": True},
             "world": _world(), "party": [], "npcs": {}}
    with audit_trace.collecting():
        combat.combat_node(state)
        entry = audit_trace.record_turn_trace(dict(state), action_id="a1")
    events = {}
    for raw in capsys.readouterr().out.splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        events[row.get("event")] = row
    assert events["combat.mechanics"]["step_count"] >= 1
    assert "rounds" in events["combat.summary"]
    assert entry["mechanics"]["steps"]
    out = json.dumps(entry["mechanics"]) + json.dumps(events["combat.mechanics"])
    assert "Goblin" not in out and NAME not in out


def test_no_names_in_trace():
    hero = _actor("player", player=True)
    foe = _actor("Nome Com Espaço", name=NAME)
    with mt.scope():
        resolve_attack(hero, foe, virtude_key="forca", rng=random.Random(1))
        mt.record_step("target_redirect", actor="player", target=NAME, reason="Texto livre")
        dump = json.dumps(mt.snapshot())
    assert NAME not in dump and "Texto livre" not in dump and "Nome Com" not in dump


def test_export_includes_mechanics_and_passes_scan():
    from services.audit_export import build_audit_bundle
    from tests.test_audit_export import GEN_AT, _crafted_state, _lines, _source
    state = _crafted_state()
    steps = [{"kind": "attack", "actor_ref": "player", "target_ref": "mon_cao_rebite",
              "dice": [7, 3], "kept": [7, 3], "modifier": 3, "dc_or_defense": 10,
              "result": "acerto", "amount": 13},
             {"kind": "damage", "target_ref": "mon_cao_rebite", "amount": 4,
              "result": "dano", "reason": "cortante"}]
    state["audit_trace"][0]["mechanics"] = {"steps": steps, "truncated": 2, "extra": "x"}
    rows = _lines(build_audit_bundle(_source(state), generated_at=GEN_AT).files, "sessions/0.jsonl")
    mech = rows[0]["mechanics"]
    assert mech["steps"][0]["dice"] == [7, 3] and mech["truncated"] == 2 and "extra" not in mech
    assert "mechanics" not in rows[1]
