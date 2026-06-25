"""
Testes da Fase 2 — mundo vivo: fações com objetivos próprios (offline, sem API key).
Núcleo determinístico: seed, avanço por tempo, backfill, persistência, integração no grafo.
"""
from langchain_core.messages import HumanMessage

import gamedata
import world_utils as wu


# --------------------------------------------------------------------------
# Seed / dados
# --------------------------------------------------------------------------
def test_factions_data_loads():
    assert gamedata.FACTIONS, "factions.json deve carregar"
    assert "culto_clareira" in gamedata.FACTIONS


def test_seed_factions_fresh_copy():
    a = gamedata.seed_factions()
    b = gamedata.seed_factions()
    assert isinstance(a, list) and len(a) >= 4
    # cada facção começa zerada e não concluída
    for f in a:
        assert f["progress"] == 0 and f["completed"] is False
        assert f["pace"] >= 1 and f["disposition"] in ("hostil", "neutro", "aliado")
    # cópias independentes (mutar uma não afeta a outra)
    a[0]["progress"] = 99
    assert b[0]["progress"] == 0


# --------------------------------------------------------------------------
# advance_factions
# --------------------------------------------------------------------------
def test_advance_factions_progresses_by_pace():
    factions = [{"id": "x", "name": "X", "goal": "g", "progress": 0,
                 "pace": 5, "disposition": "neutro", "completed": False}]
    out, events = wu.advance_factions(factions, periods=2)
    assert out[0]["progress"] == 10  # 5 * 2
    assert events == []


def test_advance_factions_zero_periods_noop():
    factions = [{"id": "x", "name": "X", "progress": 7, "pace": 5, "completed": False}]
    out, events = wu.advance_factions(factions, periods=0)
    assert out[0]["progress"] == 7 and events == []


def test_advance_factions_clamps_and_completes():
    factions = [{"id": "x", "name": "Culto", "goal": "despertar", "progress": 96,
                 "pace": 5, "disposition": "hostil", "completed": False}]
    out, events = wu.advance_factions(factions, periods=2)
    assert out[0]["progress"] == 100
    assert out[0]["completed"] is True
    assert len(events) == 1
    assert events[0]["id"] == "x" and events[0]["disposition"] == "hostil"


def test_completed_faction_does_not_readvance():
    factions = [{"id": "x", "name": "X", "progress": 100, "pace": 5, "completed": True}]
    out, events = wu.advance_factions(factions, periods=3)
    assert out[0]["progress"] == 100
    assert events == []  # já concluída → sem evento duplicado


def test_ensure_factions_backfills_empty():
    out = wu.ensure_factions([])
    assert out and all("progress" in f and "completed" in f for f in out)


def test_ensure_factions_backfills_missing_fields():
    out = wu.ensure_factions([{"id": "y", "name": "Y", "goal": "g"}])
    f = out[0]
    assert f["progress"] == 0 and f["pace"] >= 1
    assert f["disposition"] == "neutro" and f["completed"] is False


# --------------------------------------------------------------------------
# Persistência (round-trip)
# --------------------------------------------------------------------------
def test_factions_persist_round_trip(tmp_path, monkeypatch):
    import os
    import persistence
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    state = {
        "game_id": "fase2_persist",
        "narrative_summary": "", "archivist_last_run": 0, "chronicle": [],
        "messages": [], "player": {}, "world": {},
        "factions": gamedata.seed_factions(),
        "party": [], "enemies": [], "npcs": {}, "campaign_plan": {},
    }
    state["factions"][0]["progress"] = 42
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(os.path.join(str(tmp_path), "fase2_persist.json"))
    assert loaded["factions"][0]["progress"] == 42


# --------------------------------------------------------------------------
# Integração no grafo (modo simulado): descanso avança as fações
# --------------------------------------------------------------------------
def _state_for_graph(user_text: str):
    return {
        "game_id": "fase2_test",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "chronicle": [],
        "messages": [HumanMessage(content=user_text)],
        "next": "storyteller",
        "player": {
            "name": "T", "class_name": "Guerreiro", "race": "Humano",
            "hp": 10, "max_hp": 30, "mana": 5, "max_mana": 5,
            "stamina": 5, "max_stamina": 10, "gold": 10, "level": 1, "xp": 0,
            "alignment": "Neutro",
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": [], "known_abilities": [], "defense": 10,
            "attack_bonus": 0, "active_conditions": [],
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "factions": gamedata.seed_factions(),
        "campaign_plan": {}, "needs_replan": False,
        "enemies": [], "party": [], "npcs": {}, "active_npc_name": None,
        "combat_target": None, "loot_source": None,
    }


def test_graph_rest_advances_factions():
    from main import app
    result = app.invoke(_state_for_graph("vou descansar e acampar aqui"))
    factions = result.get("factions") or []
    assert factions, "estado deve conter fações após o turno"
    # descanso = 2 períodos → ao menos uma facção progrediu além de 0
    assert any(f["progress"] > 0 for f in factions), "descanso deve avançar fações"
