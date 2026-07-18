"""Suíte da spec combate-lifecycle — viagem=fuga, combate órfão expira, R5.

Offline/determinístico (MockLLM via conftest). Ver specs/combate-lifecycle.md.
"""
import random

from langchain_core.messages import HumanMessage

import agents.combat as combat
from agents.router import dm_router_node
from playtest import invariants as inv


_LOC = "pantano_melancolia"      # tem conexões no mapa de Valoria
_DEST_ID = "pm_profundezas"
_DEST_NAME = "Profundezas do Pântano"


def _world():
    return {"current_location": "Pântano da Melancolia", "current_location_id": _LOC,
            "turn_count": 3, "danger_level": 2, "visited": [_LOC]}


def _player(rooted=False):
    conds = [{"name": "Raízes", "control": "root", "duration": 3}] if rooted else []
    return {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
            "stamina": 12, "max_stamina": 12, "mana": 0,
            "attributes": {"str": 16, "dex": 14, "con": 12},
            "inventory": [], "attack_bonus": 0, "known_abilities": ["ataque_basico"],
            "active_conditions": conds, "ability_cooldowns": {}}


def _enemy(hp=14):
    return {"id": "goblin_1", "name": "Goblin 1", "hp": hp, "max_hp": hp, "defense": 11,
            "status": "ativo", "attributes": {"dex": 12, "con": 10},
            "attacks": [{"name": "Adaga", "bonus": 3, "damage": "1d4+1"}],
            "active_conditions": []}


# --- Etapa 1: gate do router ------------------------------------------------

def test_viagem_em_combate_vira_fuga():
    state = {"combat": {"active": True}, "world": _world(),
             "messages": [HumanMessage(content=f"Viajo para {_DEST_NAME}")]}
    out = dm_router_node(state)
    assert out["next"] == "combat_agent"
    assert out.get("combat_flee_attempt") is True
    assert out.get("combat_flee_destination") == _DEST_ID


def test_npc_em_combate_e_bloqueado():
    state = {"combat": {"active": True}, "world": _world(), "npcs": {"Guarda": {}},
             "messages": [HumanMessage(content="Converso com o guarda sobre o clima")]}
    out = dm_router_node(state)
    assert out["next"] == "combat_agent"        # R2: npc bloqueado durante combate
    assert not out.get("combat_flee_attempt")   # não é viagem


def test_combate_sem_ativo_usa_llm_normal():
    # Sem combate ativo, o gate NÃO intercepta (fluxo LLM/mock normal).
    state = {"combat": {"active": False}, "world": _world(),
             "messages": [HumanMessage(content="Observo o horizonte")]}
    out = dm_router_node(state)
    assert out["next"] in ("storyteller", "combat_agent", "npc_actor", "loot")


# --- Etapa 2: fuga-viagem + R5 ----------------------------------------------

def test_fuga_sucesso_viaja_e_limpa_combate():
    random.seed(3)
    state = {"game_id": "flee", "messages": [HumanMessage(content=f"Viajo para {_DEST_NAME}")],
             "player": _player(), "enemies": [_enemy()], "combat": {"active": True},
             "world": _world(), "party": [],
             "combat_flee_attempt": True, "combat_flee_destination": _DEST_ID}
    out = combat.combat_node(state)
    assert not out.get("combat", {}).get("active")          # combate limpo
    assert out.get("enemies") == []
    assert out["world"]["current_location_id"] == _DEST_ID  # viajou no mesmo turno
    assert int(out["player"]["hp"]) > 0
    assert not out.get("game_over")


def test_fuga_falha_enredado_inimigos_agem():
    random.seed(1)
    state = {"game_id": "rooted", "messages": [HumanMessage(content=f"Viajo para {_DEST_NAME}")],
             "player": _player(rooted=True), "enemies": [_enemy()], "combat": {"active": True},
             "world": _world(), "party": [],
             "combat_flee_attempt": True, "combat_flee_destination": _DEST_ID}
    out = combat.combat_node(state)
    # enredado NÃO foge → combate segue, NÃO teleporta (world inalterado = ausente
    # no dict parcial, ou com o mesmo local)
    assert out.get("world", state["world"])["current_location_id"] == _LOC
    assert out.get("combat", {}).get("active") is True


def test_fim_de_combate_zera_estado():
    # R5: herói foge (texto) com inimigo VIVO → active=False, enemies=[], target=None.
    random.seed(2)
    state = {"game_id": "r5", "messages": [HumanMessage(content="fujo e corro daqui")],
             "player": _player(), "enemies": [_enemy(hp=30)], "combat": {"active": True},
             "combat_target": "Goblin 1",
             "world": _world(), "party": []}
    out = combat.combat_node(state)
    assert out.get("combat", {}).get("active") is False
    assert out.get("enemies") == []
    assert out.get("combat_target") is None


# --- Etapa 3: expiração (R3) + invariante (R4) ------------------------------

def test_combate_orfao_expira_em_3_turnos():
    combat_state = {"active": True}
    msg = [HumanMessage(content="fico parado observando")]  # não é viagem
    out = None
    for i in range(3):
        state = {"combat": combat_state, "world": _world(), "messages": msg}
        out = dm_router_node(state)
        combat_state = out.get("combat", combat_state)
    # 3ª chamada: idle chegou a 3 → combate órfão expira
    assert out["next"] == "storyteller"
    assert out["combat"]["active"] is False
    assert out.get("enemies") == []


def test_router_reseta_idle_seria_zerado_pelo_combat_node():
    # 1ª chamada: combate segue (idle=1), rota combat_agent.
    state = {"combat": {"active": True}, "world": _world(),
             "messages": [HumanMessage(content="ataco o inimigo")]}
    out = dm_router_node(state)
    assert out["next"] == "combat_agent"
    assert out["combat"]["idle_turns"] == 1


def test_invariante_combat_zombie_dispara():
    state = {"combat": {"active": True, "idle_turns": 5}}
    viol = inv.check_combat_zombie(state, None, turn=10)
    assert viol and viol[0].check_id == "combat.zombie"
    assert viol[0].severity == "error"


def test_invariante_combat_zombie_nao_dispara_normal():
    assert inv.check_combat_zombie({"combat": {"active": True, "idle_turns": 1}}, None, 1) == []
    assert inv.check_combat_zombie({"combat": {"active": False, "idle_turns": 9}}, None, 1) == []
