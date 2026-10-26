"""SPEC-325 Fase D / R16 - reforco de `lider_matilha` (via `combat_node` real, MockLLM)."""

from __future__ import annotations

import json
import logging

import pytest
from langchain_core.messages import AIMessage

import api
from services import encounter_manifest as em
from services import reinforcements as rf
from tests.spec325_chase_helpers import chaser, narration_spy, step
from tests.spec325_helpers import lacaio, make_state, run_node

LEADER_BASE = "enemy_soldado_legiao_ferro"
PASS = {"actor_id": "player", "acao": {"kind": "pass"}}


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "on")


def _leader(vit=14, **over):
    return lacaio(
        f"{LEADER_BASE}_1",
        "Capitão Teste",
        categoria="elite",
        arquetipo="lider_matilha",
        faction="legiao_ferro",
        archetype_id=LEADER_BASE,
        hp=vit,
        max_hp=30,
        vitalidade=vit,
        max_vitalidade=30,
        **over,
    )


def _state(*, leader_vit=14, level=5, danger=3, extra=None):
    enemies = [_leader(leader_vit), *(extra or [])]
    state = make_state(enemies, "espero", declaration=PASS, player_over={"level": level})
    state["world"] = {**state["world"], "danger_level": danger}
    return state


def _next(state, out, monkeypatch, narrate=None):
    return step(state, out, monkeypatch, "espero", declaration=PASS, narrate=narrate)


def _ids(out):
    return [e["id"] for e in out["enemies"]]


def _reinf(out):
    return out["combat"].get("reinforcement") or {}


def _logs_spy():
    seen: list[list[str]] = []

    def narrate(player, enemies, logs, *a, **k):
        seen.append(list(logs))
        return "Fim."

    return narrate, seen


def _api_payload(merged, out):
    state = {**merged, **{k: v for k, v in out.items() if k != "next"}}
    state["world"] = {**state["world"], "current_location": "Montanhas Afiadas"}
    state["messages"] = [*state["messages"], AIMessage(content="Fim.")]
    return api.format_response(state).model_dump()


def test_trigger_planned_before_freeze_only_leader(monkeypatch):
    state = _state(extra=[chaser(id="e2", name="Soldado")])
    out = run_node(state, monkeypatch)
    triggers = out["combat"]["scene"]["reinforcement_triggers"]
    assert [t["leader_id"] for t in triggers] == [f"{LEADER_BASE}_1"]
    assert out["combat"]["scene"]["frozen"] is True


def test_no_trigger_without_leader(monkeypatch):
    state = make_state([chaser()], "espero", declaration=PASS)
    out = run_node(state, monkeypatch)
    assert out["combat"]["scene"].get("reinforcement_triggers") in ([], None)


def test_warn_then_fire_next_round(monkeypatch):
    state = _state()
    narrate, seen = _logs_spy()
    out = run_node(state, monkeypatch, narrate=narrate)
    assert _reinf(out)["warned_round"] == 1 and not _reinf(out)["fired"]
    assert len(out["enemies"]) == 1  # ainda nada chegou
    assert any("chama os seus" in line for line in seen[-1])
    merged, out2 = _next(state, out, monkeypatch, narrate)
    assert len(out2["enemies"]) == 2
    new = out2["enemies"][1]
    assert new["id"] == f"{rf.GENERIC_ID}_r1"
    assert _reinf(out2)["fired"] is True
    assert out2["combat"]["scene"]["positions"][new["id"]]["distance_state"] == "distante"
    assert any("chega correndo" in line for line in seen[-1])


def test_once_per_conflict(monkeypatch):
    state = _state()
    out = run_node(state, monkeypatch)
    merged, out = _next(state, out, monkeypatch)
    for _ in range(3):
        merged, out = _next(merged, out, monkeypatch)
    assert sorted(_ids(out)) == sorted([f"{LEADER_BASE}_1", f"{rf.GENERIC_ID}_r1"])
    assert out["combat"]["next_by_template"][rf.GENERIC_ID] == 1


def test_unique_instance_id_and_xp(monkeypatch):
    """SPEC-226:165: o id do reforco e unico (`_r1`) e mata com XP proprio, 1 vez."""
    state = _state()
    out = run_node(state, monkeypatch)
    merged, out2 = _next(state, out, monkeypatch)
    new = next(e for e in out2["enemies"] if e["id"].endswith("_r1"))
    assert new["id"] not in {f"{LEADER_BASE}_1", LEADER_BASE}
    assert em._base_id(new["id"]) == rf.GENERIC_ID
    new["vitalidade"] = 1
    xp_before = out2["player"].get("xp", 0)
    kill = {"actor_id": "player", "acao": {"kind": "attack", "target_id": new["id"]}}
    merged2 = {**merged, **{k: v for k, v in out2.items() if k != "next"}}
    merged2["combat_declaration"] = kill
    merged2["player"] = {**merged2["player"], "virtudes": {"forca": 9, "agilidade": 9, "corpo": 9}}
    import random

    from agents import combat as cbt

    random.seed(1)
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")
    out3 = cbt.combat_node(merged2)
    dead = next(e for e in out3["enemies"] if e["id"] == new["id"])
    assert dead.get("dead") or dead.get("status") == "morto"
    assert dead["xp_awarded"] is True
    assert out3["player"].get("xp", 0) > xp_before  # XP real do reforço, 1 vez


def test_manifest_joined(monkeypatch):
    state = _state()
    out = run_node(state, monkeypatch)
    _m, out2 = _next(state, out, monkeypatch)
    manifest = out2["combat"]["encounter"]
    new_id = f"{rf.GENERIC_ID}_r1"
    part = next(p for p in manifest["participants"] if p["participant_id"] == new_id)
    assert part["presence"] == "arrived" and part["status"] == "ativo"
    assert any(
        ev["kind"] == "joined" and ev["participant_id"] == new_id for ev in manifest["events"]
    )
    assert em.is_valid_manifest(manifest)
    # a rodada seguinte nao trata o reforco como intruso
    merged = {**state, **{k: v for k, v in out2.items() if k != "next"}}
    _m3, out3 = _next(merged, out2, monkeypatch)
    assert new_id in _ids(out3)


def test_leader_down_cancels(monkeypatch):
    state = _state(extra=[chaser(id="e2", name="Soldado")])
    out = run_node(state, monkeypatch)
    assert _reinf(out)["warned_round"] == 1
    leader = out["enemies"][0]
    leader.update(fled=True, status="fugiu")
    _m, out2 = _next(state, out, monkeypatch)
    assert _reinf(out2)["cancelled"] is True
    assert not any(i.endswith("_r1") for i in _ids(out2))


def test_leader_killed_before_arrival_cancels(monkeypatch):
    state = _state(extra=[chaser(id="e2", name="Soldado")])
    out = run_node(state, monkeypatch)
    out["enemies"][0].update(dead=True, status="morto", vitalidade=0)
    _m, out2 = _next(state, out, monkeypatch)
    assert not any(i.endswith("_r1") for i in _ids(out2))


def test_budget_caps_spawn(monkeypatch):
    state = _state(level=1, danger=1)  # orcamento 3 < elite (5) + lacaio (2)
    out = run_node(state, monkeypatch)
    assert _reinf(out)["warned_round"] == 1
    _m, out2 = _next(state, out, monkeypatch)
    assert len(out2["enemies"]) == 1 and _reinf(out2)["cancelled"] is True


def test_not_in_narration_before_warn(monkeypatch):
    """Oraculo do R5: sem aviso nao ha pista do reforco na narracao nem na API."""
    state = _state(leader_vit=30)
    narrate, seen = narration_spy()
    out = run_node(state, monkeypatch, narrate=narrate)
    blob = seen[-1] + json.dumps(_api_payload(state, out)["combat"], default=str)
    assert "reinforcement" not in blob and "reforço" not in blob and "chama os seus" not in blob
    assert "reinforcement_warning" not in _api_payload(state, out)["combat"]
    assert _reinf(out) == {}


def test_api_warning_only_between_warn_and_arrival(monkeypatch):
    state = _state()
    out = run_node(state, monkeypatch)
    assert _api_payload(state, out)["combat"]["reinforcement_warning"] is True
    merged, out2 = _next(state, out, monkeypatch)
    assert "reinforcement_warning" not in _api_payload(merged, out2)["combat"]
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "shadow")
    assert "reinforcement_warning" not in _api_payload(state, out)["combat"]


def test_off_has_no_trigger_and_no_warning(monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", "off")
    state = _state()
    out = run_node(state, monkeypatch)
    assert out["combat"]["scene"].get("reinforcement_triggers") in ([], None)
    assert _reinf(out) == {}


def _norm(out):
    res = {k: v for k, v in out.items() if k != "messages"}
    res["narr"] = [m.content for m in out.get("messages", [])]
    return json.dumps(res, default=str, sort_keys=True)


def test_shadow_logs_would_fire_only(monkeypatch, caplog):
    results = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_COMBAT_REINFORCEMENTS", mode)
        state = _state()
        with caplog.at_level(logging.INFO, logger="rpg.combat"):
            caplog.clear()
            out = run_node(state, monkeypatch)
            _m, out2 = _next(state, out, monkeypatch)
        results[mode] = _norm(out2)
        events = [r.getMessage() for r in caplog.records]
        if mode == "shadow":
            assert any("reinforcements_shadow" in e for e in events)
        else:
            assert not any("reinforcements_shadow" in e for e in events)
    assert results["off"] == results["shadow"]


def test_old_save_without_triggers_continues(monkeypatch):
    """Save de antes da spec: cena sem gatilho de lider -> o combate segue sem reforco."""
    state = _state()
    out = run_node(state, monkeypatch)
    out["combat"]["scene"]["reinforcement_triggers"] = []
    out["combat"].pop("reinforcement", None)
    _m, out2 = _next(state, out, monkeypatch)
    assert len(out2["enemies"]) == 1 and _reinf(out2) == {}


def test_template_prefers_same_faction_lacaio():
    trig = {"base_id": "enemy_bandido_capitao", "faction": "bandos_nomades", "encounter_level": 1}
    tpl = rf._template_for(trig)
    # o unico Lacaio dessa faccao e ele mesmo `lider_matilha`: nunca serve de reforco
    assert tpl["id"] == rf.GENERIC_ID and tpl["categoria"] == "lacaio"
    trig = {"base_id": "x", "faction": "clas_combate", "encounter_level": 1}
    tpl = rf._template_for(trig)
    assert tpl["categoria"] == "lacaio" and tpl["arquetipo"] != "lider_matilha"


def test_template_is_real_lacaio_not_elite_copy():
    """D-P1-2: ficha de Lacaio (Vitalidade/virtudes de Lacaio), nunca a do Elite."""
    from agents.bestiary import template_by_id

    elite = template_by_id(LEADER_BASE, encounter_level=5)
    trig = {"base_id": LEADER_BASE, "faction": "legiao_ferro", "encounter_level": 5}
    tpl = rf._template_for(trig)
    assert tpl["categoria"] == "lacaio" and tpl["id"] != LEADER_BASE
    assert sum(tpl["virtudes"].values()) < sum(elite["virtudes"].values())
    assert tpl["name"] == rf.GENERIC_NAME  # nunca o nome do lider (D-P2-2)


def test_reinforcement_is_combat_creature_not_leader(monkeypatch):
    """D-P1-1: arquetipo de combate, perfil de combate, sem cartas de comando do lider."""
    state = _state()
    out = run_node(state, monkeypatch)
    _m, out2 = _next(state, out, monkeypatch)
    new = next(e for e in out2["enemies"] if "_r" in e["id"])
    assert not rf.is_leader(new)
    assert new["categoria"] == "lacaio" and new["name"] == rf.GENERIC_NAME
    actions = {p.get("action_key") for p in new["tactical_profile"]["priorities"]}
    assert "support" not in actions and "attack" in actions
    assert not {"bst_uivo_comando", "bst_mimetismo_morto"} & set(new.get("cartas") or [])
    from services import conflict_orchestrator as orch

    scene = out2["combat"]["scene"]
    actors = {e["id"]: e for e in out2["enemies"]}
    actors["player"] = out2["player"]
    sides = {"hero": ["player"], "ally": [], "enemy": list(_ids(out2))}
    decl = orch.enemy_declaration(scene, new["id"], actors, sides)
    assert decl.acao.kind in ("attack", "card")


def test_discovery_maps_reinforcement_to_species():
    from services import discovery

    assert discovery.normalize_bestiary_id({"id": f"{LEADER_BASE}_r1"}) == LEADER_BASE
    # capanga generico (fora do bestiario) segue ad-hoc: nao entra no codex
    assert discovery.normalize_bestiary_id({"id": "capanga_do_bando_r2"}) == ""
    assert discovery.normalize_bestiary_id({"id": f"{LEADER_BASE}_2"}) == LEADER_BASE


def test_terminal_leader_cancels():
    leader = _leader(14)
    scene = {"reinforcement_triggers": rf.plan_triggers([leader], 12)}
    meta = {
        "reinforcement": {
            "trigger_id": scene["reinforcement_triggers"][0]["id"],
            "warned_round": 1,
            "fired": False,
        }
    }
    leader["estado_terminal"] = True
    assert len(rf.check(scene, {leader["id"]: leader}, meta, 2)["cancel"]) == 1
    assert not rf.acts({"status": "ativo", "last_stand_pending": True})


def test_save_load_between_warn_and_arrival(monkeypatch):
    """D-P2-3: round-trip save/load no meio do reforco; a chegada acontece uma vez."""
    import persistence

    state = _state()
    out = run_node(state, monkeypatch)
    merged = {**state, **{k: v for k, v in out.items() if k != "next"}}
    merged["game_id"] = "0b6f1c2e-3d4a-4e5f-8a9b-325325325326"
    assert persistence.save_game_state(merged)
    loaded = persistence.load_game_state(persistence.save_path(merged["game_id"]))
    assert loaded["combat"]["reinforcement"]["warned_round"] == 1
    assert loaded["combat"]["scene"]["reinforcement_triggers"]
    _m, out2 = _next(loaded, loaded, monkeypatch)
    assert sum("_r" in i for i in _ids(out2)) == 1
    assert out2["combat"]["next_by_template"]


def test_check_is_pure_and_ordered():
    leader = _leader(14)
    scene = {"reinforcement_triggers": rf.plan_triggers([leader], 12)}
    actors = {leader["id"]: leader}
    meta: dict = {}
    assert [t["leader_id"] for t in rf.check(scene, actors, meta, 1)["warn"]] == [leader["id"]]
    assert meta == {}  # nada mutado
    meta = {
        "reinforcement": {
            "trigger_id": scene["reinforcement_triggers"][0]["id"],
            "warned_round": 1,
            "fired": False,
        }
    }
    assert rf.check(scene, actors, meta, 1)["fire"] == []  # mesma rodada do aviso
    assert len(rf.check(scene, actors, meta, 2)["fire"]) == 1
    leader["fled"] = True
    assert len(rf.check(scene, actors, meta, 2)["cancel"]) == 1
