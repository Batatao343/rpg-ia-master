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


@pytest.mark.parametrize("categoria", ["lacaio", "padrao", "elite", "nomeado", "chefe"])
def test_nonlethal_every_category_incapacitated_no_npc_killed(monkeypatch, spy, categoria):
    """D2 pelo fluxo real (sem presets): Elite/Chefe/Nomeado entram em Última Ação/Terminal
    com o golpe e mesmo assim viram `incapacitado`, sem `npc_killed`."""
    monkeypatch.setattr(cbt, "_canonical_enemy_id", lambda e: "npc_nomeado")
    sheet = {"categoria": categoria}
    if categoria in ("elite", "nomeado", "chefe"):
        sheet.update(ferimento_espacos={"leve": 0, "grave": 0, "critico": 1})

    killed = run_node(make_state([lacaio(**sheet)], "ataco o goblin"), monkeypatch)
    assert any(ev["type"] == "npc_killed" for ev in killed.get("pending_world_events", []))

    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    spared = run_node(make_state([lacaio(**sheet)], INTENT), monkeypatch)
    e = spy["enemies"][0]
    assert e["status"] == "incapacitado" and not e.get("dead")
    assert not any(ev["type"] == "npc_killed" for ev in spared.get("pending_world_events", []))
    assert spy["outcome"] == "victory"
    assert spared["combat"]["result"]["participants"][0]["final_status"] == "incapacitado"


def test_nonlethal_shadow_elite_still_dies_like_off(monkeypatch, spy):
    monkeypatch.setattr(cbt, "_canonical_enemy_id", lambda e: "npc_nomeado")
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "shadow")
    sheet = {"categoria": "elite", "ferimento_espacos": {"leve": 0, "grave": 0, "critico": 1}}
    out = run_node(make_state([lacaio(**sheet)], INTENT), monkeypatch)
    assert spy["enemies"][0]["dead"]
    assert any(ev["type"] == "npc_killed" for ev in out.get("pending_world_events", []))


def test_hunt_anchor_incapacitated_counts_as_hunt_kill(monkeypatch):
    from tests.spec313_helpers import setup_env
    from tests.test_spec313_hunt import _hunt_state

    setup_env(monkeypatch)
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    st, _quest, aid = _hunt_state()
    base = make_state([lacaio(id=f"{aid}_1", name="Fera")], "derrubo a fera sem matar")
    state = {**st, **{k: v for k, v in base.items() if k not in ("world", "player")}}
    state["player"] = base["player"]
    state["world"] = {**st["world"], "turn_count": 19}
    out = run_node(state, monkeypatch)
    log = out["quests"][0]["progress_log"]
    assert [r for r in log if r["kind"] == "hunt_kill"]


def test_law_nonlethal_does_not_support_homicide():
    from services import law

    assert not law.supports("homicidio", "derrubo o guarda sem matar")
    assert not law.supports("homicidio", "Sem matar.")
    assert law.supports("homicidio", "mato o guarda")
    assert law.supports("agressao", "ataco o guarda sem matar")


def test_dossier_resistances_use_pt_br_labels(monkeypatch):
    from services import bestiary_knowledge as bk
    from services import dossiers

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "legacy")
    monkeypatch.setattr(
        bk,
        "_load_all",
        lambda **k: {"goblin": {"revealed_cards": [], "revealed_resistances": ["igneo:imune"]}},
    )
    _cards, res = dossiers._revealed_for({"id": "goblin", "archetype_id": "goblin"}, 2)
    assert res == ["Ígneo (imune)"]


def test_chip_param_declares_nonlethal_without_text(monkeypatch, spy):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", "on")
    decl = {
        "actor_id": "player",
        "acao": {"kind": "attack", "target_id": "e1", "params": {"nao_letal": True}},
    }
    run_node(make_state([lacaio()], "ataco o goblin", declaration=decl), monkeypatch)
    assert spy["enemies"][0]["status"] == "incapacitado"


def _scrub(out):
    """Retorno inteiro do nó em forma comparável (mensagens viram texto)."""
    d = dict(out)
    d["messages"] = [m.content for m in d.get("messages", [])]
    return d


def test_shadow_no_state_change(monkeypatch):
    sent = {}

    def run(mode):
        monkeypatch.setenv("RPG_COMBAT_NONLETHAL", mode)

        def narrate(*a, **k):
            sent[mode] = repr((a[2], a[4], a[5]))  # logs, intent, victory
            return "Fim."

        return run_node(make_state([lacaio()], INTENT), monkeypatch, narrate=narrate)

    off, shadow = run("off"), run("shadow")
    assert _scrub(shadow) == _scrub(off)
    assert sent["shadow"] == sent["off"]


def test_off_ignores_declaration(monkeypatch, spy):
    _run(monkeypatch, "off")
    e = spy["enemies"][0]
    assert e["dead"] and not e.get("incapacitated")


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
