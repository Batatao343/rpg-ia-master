"""SPEC-296 Etapa 3 — fuga de inimigo gera alerta e o alerta vira encontro de reforços."""

import random

from langchain_core.messages import HumanMessage

import agents.combat as combat
import world_utils as wu
from tests.test_combat_lifecycle import _DEST_ID, _DEST_NAME, _enemy, _player, _world


def _state(enemies, **over):
    st = {
        "game_id": "flee-alert",
        "messages": [HumanMessage(content="ataco o goblin")],
        "player": _player(),
        "enemies": enemies,
        "combat": {"active": True},
        "world": _world(),
        "party": [],
    }
    st.update(over)
    return st


def _force_enemy_flee(monkeypatch, mark=("fled",), ids=None):
    """Roda o round real e depois marca inimigos como fugidos/rendidos (encerra o encontro)."""
    real = combat.orch.run_round

    def wrapped(scene, actors_by_id, sides, *a, **kw):
        out = real(scene, actors_by_id, sides, *a, **kw)
        for eid in ids or sides.get("enemy", []):
            actor = actors_by_id.get(eid)
            if actor is None:
                continue
            if "fled" in mark:
                actor["fled"] = True
                actor["status"] = "fugiu"
            if "surrendered" in mark:
                actor["surrendered"] = True
                actor["status"] = "rendido"
        out["ended"] = True
        return out

    monkeypatch.setattr(combat.orch, "run_round", wrapped)


def test_enemy_flee_registers_single_alert(monkeypatch):
    random.seed(5)
    _force_enemy_flee(monkeypatch)
    e1, e2 = _enemy(), {**_enemy(), "id": "goblin_2", "name": "Goblin 2"}
    out = combat.combat_node(_state([e1, e2]))
    alerts = out["world"]["threat_alerts"]
    assert len(alerts) == 1  # 1 por encontro, mesmo com 2 fugitivos
    assert alerts[0]["hint"].startswith("Goblin")
    assert alerts[0]["turn"] == 3  # turn_count do mundo


def test_stalemate_flee_registers_alert(monkeypatch):
    """Fuga por impasse (SPEC-275) é só `fled=True` no inimigo: mesmo caminho."""
    random.seed(5)
    _force_enemy_flee(monkeypatch)
    out = combat.combat_node(_state([_enemy()]))
    assert len(out["world"]["threat_alerts"]) == 1


def test_hero_flee_no_alert():
    random.seed(3)
    state = _state(
        [_enemy()],
        messages=[HumanMessage(content=f"Viajo para {_DEST_NAME}")],
        combat_flee_attempt=True,
        combat_flee_destination=_DEST_ID,
    )
    out = combat.combat_node(state)
    assert not (out.get("world") or {}).get("threat_alerts")


def test_surrender_no_alert(monkeypatch):
    random.seed(5)
    _force_enemy_flee(monkeypatch, mark=("surrendered",))
    out = combat.combat_node(_state([_enemy()]))
    assert not (out.get("world") or {}).get("threat_alerts")


def test_flee_alert_world_unit():
    fled = {**_enemy(), "fled": True, "status": "fugiu", "faction_id": "legiao"}
    w = combat._flee_alert_world(_world(), [fled], "victory")
    assert w["threat_alerts"][0]["faction_id"] == "legiao"
    assert combat._flee_alert_world(_world(), [fled], "fled") is None
    assert combat._flee_alert_world(_world(), [_enemy()], "victory") is None


def test_alert_produces_reinforcements_encounter():
    world = _world()
    world["last_encounter_turn"] = -99
    fled = {**_enemy(), "fled": True, "status": "fugiu"}
    world = combat._flee_alert_world(world, [fled], "victory")
    enc = wu.check_encounter(world, [], {}, turn=5, player_level=3)
    assert enc and enc["reason"] == "reinforcements"
    # consumido: não repete
    assert wu.check_encounter(world, [], {}, turn=5, player_level=3) is None or (
        wu.check_encounter(world, [], {}, turn=5, player_level=3)["reason"] != "reinforcements"
    )
