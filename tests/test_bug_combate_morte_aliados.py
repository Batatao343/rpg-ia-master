"""SPEC-231 — fluxo de morte com aliados, categoria de companheiro e persistência
de aliados de cena. Offline/determinístico."""
import random

from langchain_core.messages import HumanMessage

import agents.combat as combat
import party as party_mod
from services import conflict_orchestrator as orch
from services import death_flow


def _fighter(name, *, player=False, corpo=3, categoria=None):
    a = {"id": "player" if player else name, "name": name,
         "virtudes": {"corpo": corpo, "mente": 2, "agilidade": 1},
         "class_name": "Guerreiro"}
    if categoria:
        a["categoria"] = categoria
    orch.ensure_combat_sheet(a, is_player=player)
    return a


def _fill_critical(a):
    n = a["ferimento_espacos"]["critico"]
    a["ferimentos"]["critico"] = [{"regiao": "torso"} for _ in range(n)]


# --- R1 ---
def test_ally_stabilizes_player():
    player = _fighter("Kael", player=True)
    comp = party_mod.make_companion_from_npc({"role": "guerreiro"}, "Gorim")
    player["estado_terminal"] = True
    actors = {"player": player, comp["id"]: comp}
    sides = {"hero": ["player"], "ally": [comp["id"]], "enemy": ["e1"]}
    assert orch._stabilizer_for("player", actors, sides) is comp
    out = {"terminal": ["player"], "logs": [], "deaths": []}
    orch.resolve_terminals(actors, sides, out, rng=random.Random(1))
    assert out["stabilizations"][0]["attempts"] >= 1
    assert "cause" not in out["stabilizations"][0] or \
        out["stabilizations"][0]["cause"] != "sem aliado próximo e capaz"


# --- R2 ---
def test_player_stabilizes_ally():
    player = _fighter("Kael", player=True)
    comp = party_mod.make_companion_from_npc({"role": "guerreiro"}, "Gorim")
    comp["estado_terminal"] = True
    actors = {"player": player, comp["id"]: comp}
    sides = {"hero": ["player"], "ally": [comp["id"]], "enemy": []}
    assert orch._stabilizer_for(comp["id"], actors, sides) is player


# --- R3 ---
def test_companion_has_full_death_flow_and_no_enemy_policy():
    comp = party_mod.make_companion_from_npc({"role": "guerreiro"}, "Gorim")
    assert comp["categoria"] == "companheiro"
    assert death_flow.uses_full_death_flow(comp)
    assert "pursuit_policy" not in comp
    assert "bst_defesa_instintiva" not in (comp.get("cartas") or [])
    tr = party_mod.scene_allies({"npcs": {"Bors": {
        "name": "Bors", "in_scene": True, "relationship": 8, "role": "guerreiro"}},
        "party": [], "factions": []})
    assert tr[0]["categoria"] == "companheiro"
    forced = orch.ensure_combat_sheet({"name": "X", "categoria": "padrao"}, is_ally=True)
    assert forced["categoria"] == "companheiro"


# --- R4/R5 ---
def test_scene_ally_damage_persists_between_rounds(monkeypatch):
    random.seed(3)
    npcs = {"Bors": {"name": "Bors", "in_scene": True, "relationship": 8,
                     "role": "guerreiro"}}
    player = _fighter("Kael", player=True)
    player.update({"name": "Kael", "level": 2, "inventory": [],
                   "known_abilities": ["ataque_basico"]})
    enemy = {"id": "g1", "name": "Goblin 1", "hp": 400, "max_hp": 400, "defense": 5,
             "status": "ativo", "attributes": {"dex": 12, "con": 10},
             "attacks": [{"name": "Adaga", "bonus": 0, "damage": "1d2"}],
             "active_conditions": []}
    world = {"current_location": "P", "current_location_id": "pantano_melancolia",
             "turn_count": 3, "danger_level": 2, "visited": ["pantano_melancolia"]}
    state = {"game_id": "a", "messages": [HumanMessage(content="Ataco o Goblin 1")],
             "player": player, "enemies": [enemy], "combat": {"active": True},
             "world": world, "party": [], "npcs": npcs}

    real = orch.run_round

    def damaging(scene, actors, *a, **k):
        res = real(scene, actors, *a, **k)
        for act in actors.values():
            if act.get("transient"):
                act["vitalidade"] = max(0, int(act["vitalidade"]) - 3)
        return res

    monkeypatch.setattr(orch, "run_round", damaging)
    out1 = combat.combat_node(state)
    snap1 = out1["combat"]["scene_allies"][0]
    full = snap1["max_vitalidade"]
    assert snap1["vitalidade"] <= full - 3
    assert out1["npcs"]["Bors"]["vitalidade"] == snap1["vitalidade"]
    state2 = {**state, "player": out1["player"], "enemies": out1["enemies"],
              "combat": out1["combat"], "npcs": out1["npcs"],
              "messages": [HumanMessage(content="Ataco o Goblin 1")]}
    out2 = combat.combat_node(state2)
    v2 = out2["combat"]["scene_allies"][0]["vitalidade"]
    assert v2 <= max(0, snap1["vitalidade"] - 3)   # acumula; não reinicia cheio
    assert out2["npcs"]["Bors"]["vitalidade"] == v2


# --- R6/R7 ---
def test_terminal_flags_reset_after_wound_treated():
    from services import conflict_damage
    player = _fighter("Kael", player=True)
    _fill_critical(player)
    assert death_flow.should_trigger_last_stand(player)
    death_flow.trigger_last_stand(player)
    death_flow.enter_terminal_state(player)
    helper = _fighter("Gorim", categoria="companheiro")
    res = death_flow.attempt_stabilization(player, helper, rng=random.Random(2))
    for _ in range(5):
        if res.get("revived"):
            break
        res = death_flow.attempt_stabilization(player, helper, rng=random.Random(9))
    if not res.get("revived"):
        death_flow._revive(player, minimum_one=True)
    # R7: episódio terminou -> contador zerado; R6/sem imortalidade: Crítico cheio
    assert player["stabilization_attempts"] == 0
    assert player["last_stand_resolved"] is True
    assert not death_flow.should_trigger_last_stand(player)
    # trata o Crítico (Médico com kit)
    conflict_damage.rest_treat_wounds(player, "longo", has_kit=True, is_medic=True)
    assert player["ferimentos"]["critico"] == []
    assert player["last_stand_resolved"] is False
    _fill_critical(player)
    assert death_flow.should_trigger_last_stand(player)


# --- R8 ---
def test_estabilizar_card_registers_scar():
    from services import conflict_turn
    src = _fighter("Gorim", categoria="companheiro")
    tgt = _fighter("Kael", player=True)
    tgt["estado_terminal"] = True
    tgt["last_stand_pending"] = True
    out = {"logs": []}
    step = type("S", (), {"target_id": "player", "card_id": "x"})()
    conflict_turn._resolve_support_card(
        {}, src, "Gorim", {"player": tgt, "Gorim": src}, step,
        {"name": "Estabilizar", "efeito": {"kind": "estabilizar"}}, out)
    assert out.get("scars_pending") == ["player"]
    assert tgt["last_stand_pending"] is False


# --- R9 ---
def test_solo_death_unchanged():
    player = _fighter("Kael", player=True)
    player["estado_terminal"] = True
    actors = {"player": player}
    sides = {"hero": ["player"], "ally": [], "enemy": ["e1"]}
    assert orch._stabilizer_for("player", actors, sides) is None
    out = {"terminal": ["player"], "logs": [], "deaths": []}
    orch.resolve_terminals(actors, sides, out, rng=random.Random(1))
    assert out["player_dead"] is True


# --- R8 (revisão Sol): scars_pending da carta sobe do turno para a rodada ---
def test_estabilizar_card_scar_reaches_round_out(monkeypatch):
    from services import conflict_turn as ct
    src = _fighter("Gorim", categoria="companheiro")
    tgt = _fighter("Kael", player=True)
    actors = {"player": tgt, "Gorim": src}
    sides = {"hero": ["player"], "ally": ["Gorim"], "enemy": []}

    def fake_resolve_turn(scene, actors_by_id, decl, **k):
        return {"logs": [], "attacks": [], "deaths": [], "terminal": [],
                "cards_used": [], "scars_pending": ["player"]}

    monkeypatch.setattr(ct, "resolve_turn", fake_resolve_turn)
    out = {"logs": [], "deaths": [], "terminal": []}
    decl = ct.TurnDeclaration(actor_id="Gorim")
    orch._resolve_actor_turn({}, src, "Gorim", actors, sides, decl, None, out,
                             random.Random(1))
    assert out.get("scars_pending") == ["player"]


def test_transient_ally_death_records_died_turn():
    from agents.combat import _reflect_scene_allies
    state = {"world": {"turn_count": 12},
             "npcs": {"Bors": {"name": "Bors", "in_scene": True, "vitalidade": 5}}}
    dead = {"name": "Bors", "vitalidade": 0, "max_vitalidade": 10, "dead": True}
    out = _reflect_scene_allies(state, [dead], [dead], combat_over=False)
    assert out["Bors"]["status"] == "morto"
    assert out["Bors"]["in_scene"] is False
    assert out["Bors"]["died_turn"] == 12
