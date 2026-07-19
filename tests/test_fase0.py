"""
Testes da Fase 0 — fundação de mundo (offline, sem API key).
Mundo estruturado, relógio, viagem (fog of war), descanso, temas de classe.
"""
from langchain_core.messages import HumanMessage, SystemMessage

import gamedata
import world_utils as wu


# --------------------------------------------------------------------------
# Mapa / gamedata
# --------------------------------------------------------------------------
def test_world_map_loads():
    assert gamedata.WORLD_MAP.get("locations")
    assert gamedata.START_LOCATION_ID == "nova_arcadia"


def test_get_location_and_connections():
    loc = gamedata.get_location("nova_arcadia")
    assert loc["name"] == "Nova Arcádia"
    conns = {c["id"] for c in gamedata.get_connections("nova_arcadia")}
    assert "na_anel_lama" in conns and "pradaria_ruinas" in conns


def test_start_location_for_region():
    assert gamedata.start_location_for_region("Skallgard")["id"] == "skallgard"
    assert gamedata.start_location_for_region("Floresta dos Sussurros")["id"] == "floresta_sussurros"


# --------------------------------------------------------------------------
# Relógio
# --------------------------------------------------------------------------
def test_advance_clock_wraps_day():
    w = {"world_clock": {"day": 1, "period": "Noite"}}
    wu.advance_clock(w, 1)  # Noite -> Amanhecer do dia 2
    assert w["world_clock"] == {"day": 2, "period": "Amanhecer"}


def test_ensure_world_backfills():
    w = wu.ensure_world({"current_location": "Nova Arcádia"})
    assert w["current_location_id"] == "nova_arcadia"
    assert "nova_arcadia" in w["visited"]
    assert w["world_clock"]["period"] in wu.PERIODS


# --------------------------------------------------------------------------
# Viagem (fog of war)
# --------------------------------------------------------------------------
def test_find_travel_destination_connected():
    w = wu.ensure_world({"current_location_id": "nova_arcadia"})
    dest = wu.find_travel_destination(w, "vou para o Anel de Lama")
    assert dest and dest["id"] == "na_anel_lama"


def test_find_travel_destination_rejects_unconnected():
    w = wu.ensure_world({"current_location_id": "nova_arcadia"})
    # Skallgard não conecta direto a Nova Arcádia (fica além das Montanhas Afiadas)
    assert wu.find_travel_destination(w, "vou para Skallgard") is None


def test_apply_travel_reveals_and_advances():
    w = wu.ensure_world({"current_location_id": "nova_arcadia"})
    period0 = w["world_clock"]["period"]
    w2 = wu.apply_travel(w, gamedata.get_location("pradaria_ruinas"))
    assert w2["current_location_id"] == "pradaria_ruinas"
    assert "pradaria_ruinas" in w2["visited"]
    assert w2["world_clock"]["period"] != period0  # tempo passou


# --------------------------------------------------------------------------
# Descanso
# --------------------------------------------------------------------------
def test_apply_rest_heals_and_passes_time():
    player = {"hp": 1, "max_hp": 40, "mana": 0, "max_mana": 10, "stamina": 0, "max_stamina": 20}
    w = wu.ensure_world({"current_location_id": "nova_arcadia"})
    p2, w2 = wu.apply_rest(player, w)
    assert p2["hp"] > 1 and p2["hp"] <= 40
    assert p2["stamina"] > 0
    assert w2["world_clock"] != w["world_clock"]


def test_is_rest_detection():
    assert wu.is_rest("vou descansar um pouco")
    assert wu.is_rest("acampo aqui")
    assert not wu.is_rest("ataco o goblin")


# --------------------------------------------------------------------------
# Temas de classe (gating)
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# starting_world
# --------------------------------------------------------------------------
def test_starting_world_shape():
    w = wu.starting_world("Montanhas Afiadas", level=3)
    assert w["current_location_id"] == "montanhas_afiadas"
    assert w["visited"] == ["montanhas_afiadas"]
    assert w["world_clock"]["day"] == 1


# --------------------------------------------------------------------------
# Integração: grafo end-to-end (modo simulado) com viagem
# --------------------------------------------------------------------------
def _state_for_graph():
    return {
        "game_id": "fase0_test",
        "narrative_summary": "",
        "archivist_last_run": 0,
        "messages": [HumanMessage(content="vou para a Pradaria das Ruínas")],
        "next": "storyteller",
        "player": {
            "name": "T", "class_name": "Guerreiro", "race": "Humano",
            "hp": 30, "max_hp": 30, "mana": 5, "max_mana": 5,
            "stamina": 10, "max_stamina": 10, "gold": 10, "level": 1, "xp": 0,
            "alignment": "Neutro",
            "attributes": {"str": 12, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": [], "known_abilities": [], "defense": 10,
            "attack_bonus": 0, "active_conditions": [],
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "campaign_plan": {}, "needs_replan": False,
        "enemies": [], "party": [], "npcs": {}, "active_npc_name": None,
        "combat_target": None, "loot_source": None,
    }


def test_graph_travel_end_to_end():
    from main import app
    result = app.invoke(_state_for_graph())
    w = result["world"]
    assert w["current_location_id"] == "pradaria_ruinas"
    assert "pradaria_ruinas" in w["visited"]
