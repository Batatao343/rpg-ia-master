"""Suíte da spec aliados-em-combate — aliado presente entra no combate.

Offline/determinístico (MockLLM via conftest). Ver specs/SPEC-055-aliados-em-combate.md.
"""
import random

from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
import party as party_mod
from playtest import invariants as inv
from playtest.profiles import Recrutador


_LOC = "pantano_melancolia"


def _world():
    return {"current_location": "Pântano", "current_location_id": _LOC,
            "turn_count": 3, "danger_level": 2, "visited": [_LOC]}


def _player():
    return {"name": "Kael", "class_name": "Guerreiro", "hp": 30, "max_hp": 30,
            "stamina": 12, "max_stamina": 12, "mana": 0, "level": 2,
            "attributes": {"str": 16, "dex": 14, "con": 12},
            "inventory": [], "attack_bonus": 0, "known_abilities": ["ataque_basico"],
            "active_conditions": [], "ability_cooldowns": {}}


def _enemy(hp=14):
    return {"id": "goblin_1", "name": "Goblin 1", "hp": hp, "max_hp": hp, "defense": 11,
            "status": "ativo", "attributes": {"dex": 12, "con": 10},
            "attacks": [{"name": "Adaga", "bonus": 3, "damage": "1d4+1"}],
            "active_conditions": []}


# --- R1: companheiro ativo já luta (regressão travada) ----------------------

def test_companheiro_ativo_luta():
    comp = party_mod.make_companion_from_npc({"role": "guerreiro"}, "Gorim")
    st = {"party": [comp], "npcs": {}}
    assert any(a.get("name") == "Gorim" for a in party_mod.active_allies(st))


# --- R2: amigo em cena vira aliado transitório ------------------------------

def test_npc_amigo_em_cena_vira_aliado():
    npcs = {"Bors": {"name": "Bors", "in_scene": True, "relationship": 7,
                     "role": "guerreiro"}}
    tr = party_mod.scene_allies({"npcs": npcs, "party": [], "factions": []})
    assert [a["name"] for a in tr] == ["Bors"]
    assert tr[0]["transient"] is True


def test_npc_frio_ou_hostil_nao_entra():
    npcs = {
        "Frio": {"name": "Frio", "in_scene": True, "relationship": 3, "role": "guarda"},
        "Traidor": {"name": "Traidor", "in_scene": True, "relationship": 9,
                    "role": "guarda", "faction": "legiao"},
    }
    factions = [{"id": "legiao", "disposition": "hostil"}]
    tr = party_mod.scene_allies({"npcs": npcs, "party": [], "factions": factions})
    assert tr == []


def test_npc_fora_de_cena_nao_entra():
    npcs = {"Ausente": {"name": "Ausente", "in_scene": False, "relationship": 8,
                        "role": "guerreiro"}}
    assert party_mod.scene_allies({"npcs": npcs, "party": [], "factions": []}) == []


def test_npc_alvo_do_encontro_nao_vira_aliado():
    npcs = {"Bors": {"name": "Bors", "id": "npc_bors", "in_scene": True,
                     "relationship": 9, "role": "guerreiro"}}
    state = {"npcs": npcs, "party": [], "factions": []}
    assert party_mod.scene_allies(state, excluded=["Bors", "npc_bors"]) == []


def test_teto_aliados_transitorios():
    npcs = {f"Amigo{i}": {"name": f"Amigo{i}", "in_scene": True, "relationship": 8,
                          "role": "guerreiro"} for i in range(4)}
    tr = party_mod.scene_allies({"npcs": npcs, "party": [], "factions": []})
    assert len(tr) == party_mod.MAX_SCENE_ALLIES


def test_ja_recrutado_nao_duplica():
    npcs = {"Gorim": {"name": "Gorim", "in_scene": True, "relationship": 9,
                      "role": "guerreiro", "id": "npc_gorim"}}
    party = [party_mod.make_companion_from_npc(npcs["Gorim"], "Gorim")]
    tr = party_mod.scene_allies({"npcs": npcs, "party": party, "factions": []})
    assert tr == []


# --- R2/R3: aliado transitório luta no combate e não persiste ---------------

def test_aliado_transitorio_entra_no_combate_e_nao_persiste():
    random.seed(2)
    npcs = {"Bors": {"name": "Bors", "in_scene": True, "relationship": 8,
                     "role": "guerreiro"}}
    state = {"game_id": "ally", "messages": [HumanMessage(content="Ataco o Goblin 1")],
             "player": _player(), "enemies": [_enemy(hp=40)], "combat": {"active": True},
             "world": _world(), "party": [], "npcs": npcs}
    out = combat.combat_node(state)
    # Iniciativa v4 é por LADO; Bors fica registrado entre os aliados da cena e
    # age no lado "heroes".
    meta = out.get("combat") or {}
    assert "heroes" in (meta.get("initiative") or [])
    assert any(a.get("name") == "Bors" for a in (meta.get("scene_allies") or []))
    # transitório NÃO virou party permanente
    assert out.get("party") == []


def test_dano_e_morte_transitorios_refletem_no_npc():
    npc = {"name": "Bors", "in_scene": True, "relationship": 8,
           "role": "guerreiro", "hp": 12, "max_hp": 12}
    state = {"npcs": {"Bors": npc}}
    transient = {"name": "Bors", "origin_npc": "Bors", "transient": True}
    live = {**transient, "vitalidade": 0, "max_vitalidade": 12,
            "dead": True, "status": "morto"}
    reflected = combat._reflect_scene_allies(state, [transient], [live], True)
    assert reflected["Bors"]["status"] == "morto"
    assert reflected["Bors"]["hp"] == 0
    assert reflected["Bors"]["in_scene"] is False


# --- R5: invariante de aliado fantasma --------------------------------------

def _combat_state_with_narr(narr, party=None, npcs=None):
    return {"combat": {"active": True},
            "messages": [HumanMessage(content="ataco"), AIMessage(content=narr)],
            "party": party or [], "npcs": npcs or {}, "factions": []}


def test_phantom_ally_detecta():
    # Companheiro benched (inactive) citado como lutando → fantasma.
    party = [{"name": "Korvus", "active": False, "status": "ativo", "hp": 10,
              "id": "c1"}]
    st = _combat_state_with_narr("Korvus ergue o escudo e avança ao seu lado.",
                                 party=party)
    viol = inv.check_phantom_ally(st, None, 5)
    assert viol and viol[0].check_id == "combat.phantom_ally"


def test_phantom_ally_silencia_com_aliado_presente():
    npcs = {"Bors": {"name": "Bors", "in_scene": True, "relationship": 8,
                     "role": "guerreiro"}}
    st = _combat_state_with_narr("Bors crava a lâmina no inimigo ao seu lado.",
                                 npcs=npcs)
    assert inv.check_phantom_ally(st, None, 5) == []


def test_perfil_recrutador_exercita_transitorio_e_party():
    profile = Recrutador()
    rng = random.Random(1)
    scene = {"npcs": {"Bors": {"name": "Bors", "in_scene": True,
                                "relationship": party_mod.SCENE_ALLY_MIN_REL}},
             "party": []}
    assert "combate" in profile._next_action(scene, rng)
    assert "Converso" in profile._next_action(scene, rng)
    scene["npcs"]["Bors"]["relationship"] = party_mod.RECRUIT_MIN_REL
    recruit_action = profile._next_action(scene, rng)
    assert party_mod.detect_party_command(recruit_action) == "recruit"
    scene["party"] = [party_mod.make_companion_from_npc(
        scene["npcs"]["Bors"], "Bors")]
    assert "combate" in profile._next_action(scene, rng)
    profile.reset()
    scene["party"] = []
    scene["npcs"]["Bors"]["relationship"] = party_mod.SCENE_ALLY_MIN_REL
    assert "combate" in profile._next_action(scene, rng)
