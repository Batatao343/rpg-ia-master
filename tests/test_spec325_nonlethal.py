"""SPEC-325 Fase A / R9 - golpe nao-letal pelo `combat_node` real."""

from __future__ import annotations

import pytest

from agents import combat as cbt
from services import companion_tags
from services import conflict_orchestrator as orch
from services import encounter_manifest as em
from tests.spec325_helpers import lacaio, make_state, run_node

INTENT = "derrubo o goblin sem matar"


@pytest.fixture
def spy(monkeypatch):
    """Captura a lista de inimigos final (o nó devolve [] quando o combate acaba)."""
    seen = {}
    real = cbt._finish_encounter

    def wrapped(meta, enemies, outcome, *, loot):
        seen["enemies"] = enemies
        seen["outcome"] = outcome
        seen["loot"] = loot
        return real(meta, enemies, outcome, loot=loot)

    monkeypatch.setattr(cbt, "_finish_encounter", wrapped)
    return seen


def _run(monkeypatch, mode, intent=INTENT):
    if mode:
        monkeypatch.setenv("RPG_COMBAT_NONLETHAL", mode)
    return run_node(make_state([lacaio()], intent), monkeypatch)


def _elite():
    return {
        "id": "el",
        "name": "Elite",
        "categoria": "elite",
        "status": "ativo",
        "last_stand_resolved": True,
        "ferimento_espacos": {"leve": 1, "grave": 1, "critico": 1},
        "ferimentos": {"leve": [], "grave": [], "critico": [{"x": 1}]},
    }


def test_lacaio_nonlethal_incapacitated_not_dead(monkeypatch, spy):
    out = _run(monkeypatch, "on")
    e = spy["enemies"][0]
    assert e["status"] == "incapacitado" and e["incapacitated"] and not e.get("dead")
    assert e["nonlethal_by"] == "player"
    assert spy["outcome"] == "victory" and spy["loot"] is True
    assert out["next"] == "loot"
    assert out["combat"]["result"]["participants"][0]["final_status"] == "incapacitado"


def test_lethal_without_declaration_still_kills(monkeypatch, spy):
    _run(monkeypatch, "on", intent="ataco o goblin")
    e = spy["enemies"][0]
    assert e["dead"] and e["status"] == "morto" and not e.get("incapacitated")


def test_outcome_victory_not_defeat_with_incapacitated():
    enemy = {"id": "e1", "status": "incapacitado", "incapacitated": True}
    out = cbt._encounter_outcome(
        player={"conscious": True}, enemies=[enemy], hero_fled=False, player_dead=False
    )
    assert out == "victory"


def test_mirror_vitals_keeps_incapacitated_status():
    e = {"id": "e1", "vitalidade": 0, "incapacitated": True, "nonlethal_by": "player"}
    cbt._mirror_vitals(e)
    assert e["status"] == "incapacitado"
    # sem a marca do golpe nao-letal (ex.: protagonista incapacitado), nada muda
    p = {"vitalidade": 5, "incapacitated": True}
    cbt._mirror_vitals(p)
    assert p["status"] == "ativo"


def test_xp_once_on_incapacitation(monkeypatch, spy):
    out = _run(monkeypatch, "on")
    assert out["player"]["xp"] == 50  # mesmo XP do abate de lacaio (D2)
    assert spy["enemies"][0]["xp_awarded"] is True


def test_xp_same_as_kill(monkeypatch):
    killed = run_node(make_state([lacaio()], "ataco o goblin"), monkeypatch)
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    spared = run_node(make_state([lacaio()], INTENT), monkeypatch)
    assert killed["player"]["xp"] == spared["player"]["xp"] == 50


def test_no_npc_killed_event_and_named_npc_survives(monkeypatch):
    monkeypatch.setattr(cbt, "_canonical_enemy_id", lambda e: "npc_nomeado")
    killed = run_node(make_state([lacaio()], "ataco o goblin"), monkeypatch)
    assert any(ev["type"] == "npc_killed" for ev in killed.get("pending_world_events", []))
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    state = make_state([lacaio()], INTENT)
    state["npcs"] = {"Nomeado": {"id": "npc_nomeado", "name": "Nomeado"}}
    spared = run_node(state, monkeypatch)
    assert not any(ev["type"] == "npc_killed" for ev in spared.get("pending_world_events", []))
    assert "npc_nomeado" in {n["id"] for n in state["npcs"].values()}


def test_chip_param_declares_nonlethal_without_text(monkeypatch, spy):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    decl = {
        "actor_id": "player",
        "acao": {"kind": "attack", "target_id": "e1", "params": {"nao_letal": True}},
    }
    run_node(make_state([lacaio()], "ataco o goblin", declaration=decl), monkeypatch)
    assert spy["enemies"][0]["status"] == "incapacitado"


def test_shadow_no_state_change(monkeypatch):
    off = _run(monkeypatch, "off")
    shadow = _run(monkeypatch, "shadow")
    assert shadow["combat"] == off["combat"]
    assert shadow["player"] == off["player"]
    assert shadow.get("pending_world_events") == off.get("pending_world_events")
    assert shadow["messages"][0].content == off["messages"][0].content


def test_off_ignores_declaration(monkeypatch, spy):
    _run(monkeypatch, "off")
    e = spy["enemies"][0]
    assert e["dead"] and not e.get("incapacitated")


def test_elite_nonlethal_after_last_stand():
    elite = _elite()
    out = {"deaths": [], "terminal": [], "logs": []}
    orch._check_terminal(elite, "el", out, damage_applied=True, nonlethal="on", by="player")
    assert elite["status"] == "incapacitado" and not elite.get("dead")
    assert out["deaths"] == [] and out["incapacitated"] == ["el"]


def test_elite_without_flag_still_dies_after_last_stand():
    elite = _elite()
    out = {"deaths": [], "terminal": [], "logs": []}
    orch._check_terminal(elite, "el", out, damage_applied=True)
    assert elite["dead"] and out["deaths"] == ["el"]


def test_lethal_form_still_kills(monkeypatch):
    from services import cards
    from services.conflict_turn import TurnStep

    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    monkeypatch.setattr(
        cards, "get_card", lambda cid: {"efeito": {"kind": "destruicao_total"}} if cid else None
    )
    sides = {"hero": ["player"], "ally": [], "enemy": ["e1"]}
    step = TurnStep(kind="card", card_id="c", target_id="e1", params={"nao_letal": True})
    assert orch._nonlethal_mode(None, step, "player", "e1", sides) == ""
    monkeypatch.setattr(cards, "get_card", lambda cid: {"efeito": {"kind": "dano"}})
    assert orch._nonlethal_mode(None, step, "player", "e1", sides) == "on"
    # nunca para inimigo declarando, nem contra aliado
    assert orch._nonlethal_mode(None, step, "e1", "e1", sides) == ""
    assert orch._nonlethal_mode(None, step, "player", "bors", sides) == ""


def test_companion_tag_poupou_inimigo():
    result = {
        "encounter_id": "x",
        "participants": [{"participant_id": "e1", "final_status": "incapacitado"}],
    }
    state = {
        "combat": {"phase": "ended", "outcome": "victory", "result": result},
        "player": {},
    }
    ids = [t["id"] for t in companion_tags.detect_choice_tags(state)]
    assert "poupou_inimigo" in ids
    killed = {
        "combat": {
            "phase": "ended",
            "outcome": "victory",
            "result": {"encounter_id": "x", "participants": [{"final_status": "morto"}]},
        },
        "player": {},
    }
    assert "poupou_inimigo" not in [t["id"] for t in companion_tags.detect_choice_tags(killed)]


def test_manifest_incapacitated_event():
    enemy = {"id": "e1", "name": "Goblin", "categoria": "lacaio", "status": "ativo"}
    manifest = em.build_manifest([enemy], source="systemic", origin="test", encounter_id="enc1")
    enemy.update({"incapacitated": True, "status": "incapacitado", "nonlethal_by": "player"})
    manifest = em.sync_statuses(manifest, [enemy], 2)
    assert manifest["participants"][0]["status"] == "incapacitado"
    assert [ev["kind"] for ev in manifest["events"]][-1] == "incapacitated"


def test_old_save_status_ativo_loads(monkeypatch):
    """Save antigo (sem campos novos) segue: inimigo ativo continua ativo."""
    e = lacaio(vitalidade=30, max_vitalidade=30)
    cbt._mirror_vitals(e)
    assert e["status"] == "ativo"
    big = lacaio(vitalidade=30, max_vitalidade=30, hp=30, max_hp=30)
    out = run_node(make_state([big]), monkeypatch)
    assert "next" in out


def test_api_nonlethal_available_only_when_on(monkeypatch):
    import api

    state = make_state([lacaio()])
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "shadow")
    assert "nonlethal_available" not in api._combat_block(state)
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    assert api._combat_block(state)["nonlethal_available"] is True
