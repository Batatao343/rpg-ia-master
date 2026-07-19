"""
Fase 4.5 — Party: aliados em combate.
Spec: specs/fase-4.5-party-aliados.md. 100% offline.
"""
import pytest

import combat_mechanics as cm
import party as pt


def make_player(**over):
    p = {
        "name": "Testo", "class_name": "", "race": "Humano", "level": 3, "xp": 0,
        "hp": 40, "max_hp": 40, "mana": 10, "max_mana": 10,
        "stamina": 20, "max_stamina": 20, "gold": 0,
        "attributes": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "inventory": [], "equipment": {"weapon": None, "armor": None, "accessory": None},
        "known_abilities": ["ataque_basico"], "defense": 13, "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {}, "pending_choices": [],
    }
    p.update(over)
    return p


def make_enemy(i=1, **over):
    e = {
        "id": f"enemy_orc_{i}", "name": f"Orc {i}", "type": "Minion",
        "hp": 12, "max_hp": 12, "defense": 10, "status": "ativo",
        "attributes": {"str": 12, "dex": 10, "con": 10},
        "active_conditions": [],
        "attacks": [{"name": "Machado", "type": "melee", "bonus": 3, "damage": "1d6+1"}],
        "stamina": 0, "mana": 0, "attack_mod": 0,
        "behavior": {"profile": "feroz"},
    }
    e.update(over)
    return e


def make_npc(name="Grom", rel=8, role="guerreiro veterano da Legião"):
    return {"id": "", "name": name, "role": role, "persona": "leal",
            "relationship": rel, "memory": [],
            "attributes": {"str": 14, "dex": 10, "con": 12},
            "combat_stats": {"hp": 20, "ac": 13,
                             "attacks": [{"name": "Espada", "type": "melee",
                                          "bonus": 4, "damage": "1d8+2"}]}}


# ---------------------------------------------------------------------------
# Etapa 1 — ficha/arquétipos
# ---------------------------------------------------------------------------

def test_make_companion_arquetipo():
    c = pt.make_companion_from_npc(make_npc(role="arqueira dos bandos nômades"), "Lira")
    assert c["archetype"] == "arqueiro"
    assert c["hp"] == 20  # combat_stats do NPC têm prioridade
    assert c["attacks"]


def test_make_companion_fallback_capanga():
    c = pt.make_companion_from_npc({"role": "pescador"}, "Zé")
    assert c["archetype"] == "capanga"
    assert c["hp"] > 0 and c["attacks"]


def test_companions_json_schema():
    assert set(pt.COMPANION_TEMPLATES) >= {"guerreiro", "arqueiro", "curandeiro", "mago", "capanga"}
    for arch, t in pt.COMPANION_TEMPLATES.items():
        assert t["hp"] > 0 and t["attacks"], arch
        assert t["behavior"]["profile"] in ("tatico", "feroz", "covarde", "implacavel")


# ---------------------------------------------------------------------------
# Etapa 2 — recrutamento/comandos (gates Python)
# ---------------------------------------------------------------------------

def _state(**over):
    s = {"npcs": {}, "party": [], "factions": [], "world": {"current_location": "Skallgard"}}
    s.update(over)
    return s


def test_can_recruit_relationship_baixo_nega():
    s = _state(npcs={"Grom": make_npc(rel=4)})
    ok, reason = pt.can_recruit(s, "Grom")
    assert not ok and "confia" in reason


def test_can_recruit_teto_3():
    party = [pt.make_companion_from_npc(make_npc(), f"C{i}") for i in range(3)]
    s = _state(npcs={"Grom": make_npc(rel=9)}, party=party)
    ok, reason = pt.can_recruit(s, "Grom")
    assert not ok and "cheio" in reason


def test_can_recruit_faccao_hostil_nega():
    npc = make_npc(rel=9)
    npc["faction"] = "mao_sombria"
    s = _state(npcs={"Grom": npc}, factions=[{"id": "mao_sombria", "disposition": "hostil"}])
    ok, reason = pt.can_recruit(s, "Grom")
    assert not ok and "hostil" in reason


def test_recruit_e_dismiss():
    s = _state(npcs={"Grom": make_npc(rel=9)})
    new_party, reason = pt.recruit(s, "Grom")
    assert new_party and new_party[0]["name"] == "Grom"
    s["party"] = new_party
    after, found = pt.dismiss(s, "grom")  # case-insensitive
    assert found and after == []


def test_esperar_seguir():
    s = _state(party=[pt.make_companion_from_npc(make_npc(), "Grom")])
    waited, found = pt.set_waiting(s, "Grom", "Skallgard")
    assert found and not waited[0]["active"] and waited[0]["waiting_at"] == "Skallgard"
    s["party"] = waited
    back, found2 = pt.set_following(s, "Grom")
    assert found2 and back[0]["active"]


def test_detect_party_command():
    assert pt.detect_party_command("Grom, junte-se a mim!") == "recruit"
    assert pt.detect_party_command("espere aqui, Grom") == "wait"
    assert pt.detect_party_command("você está dispensado") == "dismiss"
    assert pt.detect_party_command("qual o preço do pão?") is None


# ---------------------------------------------------------------------------
# Etapa 3 — combate N vs N
# ---------------------------------------------------------------------------

def test_iniciativa_inclui_aliados():
    allies = [pt.make_companion_from_npc(make_npc(), "Grom")]
    order = cm.roll_initiative(make_player(), [make_enemy()], allies)
    sides = {o["side"] for o in order}
    assert sides == {"hero", "ally", "enemy"}


def test_ally_turn_ataca(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 15)
    ally = pt.make_companion_from_npc(make_npc(), "Grom")
    e = make_enemy(hp=100, max_hp=100, defense=5)
    logs = cm.resolve_ally_turn(ally, [e])
    assert e["hp"] < 100
    assert any("Grom" in l for l in logs)


def test_pick_target_tatico_menor_hp():
    enemy = make_enemy(behavior={"profile": "tatico"})
    p = make_player(hp=40, max_hp=40)
    ally = pt.make_companion_from_npc(make_npc(), "Grom")
    ally["hp"] = 2  # 10% — alvo óbvio do tático
    tgt = cm.pick_target(enemy, [p, ally])
    assert tgt is ally


def test_pick_target_implacavel_player():
    enemy = make_enemy(behavior={"profile": "implacavel"})
    p = make_player(hp=1)
    ally = pt.make_companion_from_npc(make_npc(), "Grom")
    tgt = cm.pick_target(enemy, [p, ally])
    assert tgt is p


def test_enemy_pode_matar_aliado(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 19 if b == 20 else b)
    enemy = make_enemy(behavior={"profile": "tatico"})
    p = make_player()
    ally = pt.make_companion_from_npc(make_npc(), "Grom")
    ally["hp"] = 1
    logs = cm.resolve_enemy_turn(enemy, p, allies=[enemy], rnd=1, hero_side=[p, ally])
    assert ally["status"] == "morto" and not ally["active"]
    assert any("CAI" in l for l in logs)
    assert p["hp"] == 40  # player intocado


def test_4v5_sem_crash():
    """Critério da Fase 4: eu + 3 companions vs 5 orcs resolve sem exceção."""
    import random as _r
    _r.seed(7)
    p = make_player()
    allies = [pt.make_companion_from_npc(make_npc(), f"Aliado {i}") for i in range(3)]
    enemies = [make_enemy(i) for i in range(1, 6)]
    order = cm.roll_initiative(p, enemies, allies)
    assert len(order) == 9
    for rnd in range(1, 30):
        for slot in order:
            if slot["side"] == "hero":
                if p["hp"] > 0:
                    cm.resolve_player_action(
                        p, enemies, {"ability_id": "ataque_basico", "target": "",
                                     "is_allowed": True}, __import__("gamedata").ABILITIES)
            elif slot["side"] == "ally":
                a = next((x for x in allies if x["id"] == slot["id"]), None)
                if a:
                    cm.resolve_ally_turn(a, enemies, rnd)
            else:
                e = next((x for x in enemies if x["id"] == slot["id"]), None)
                if e and e.get("status") == "ativo" and p["hp"] > 0:
                    hero_side = [p] + [a for a in allies
                                       if a.get("status") == "ativo" and a["hp"] > 0]
                    cm.resolve_enemy_turn(e, p, allies=enemies, rnd=rnd, hero_side=hero_side)
        if not [e for e in enemies if e.get("status") == "ativo"] or p["hp"] <= 0:
            break
    # terminou de algum jeito coerente, sem exception
    assert p["hp"] >= 0 and all(e["hp"] >= 0 for e in enemies)


# ---------------------------------------------------------------------------
# Etapa 4 — morte de aliado alimenta o mundo (nó de combate)
# ---------------------------------------------------------------------------

def test_npc_intercept_recruit(monkeypatch):
    from agents import npc as npc_mod
    from langchain_core.messages import HumanMessage
    state = {"messages": [HumanMessage(content="Grom, junte-se a mim!")],
             "active_npc_name": "Grom",
             "npcs": {"Grom": make_npc(rel=9)}, "party": [], "factions": [],
             "world": {"current_location": "Skallgard"}}
    out = npc_mod.npc_actor_node(state)
    assert out.get("party") and out["party"][0]["name"] == "Grom"


def test_npc_intercept_recusa(monkeypatch):
    from agents import npc as npc_mod
    from langchain_core.messages import HumanMessage
    state = {"messages": [HumanMessage(content="junte-se a mim")],
             "active_npc_name": "Grom",
             "npcs": {"Grom": make_npc(rel=2)}, "party": [], "factions": [],
             "world": {"current_location": "Skallgard"}}
    out = npc_mod.npc_actor_node(state)
    assert "party" not in out
    assert "recusa" in out["messages"][0].content


def test_backfill_party_antiga():
    old = [{"name": "Velho", "hp": 9, "max_hp": 12, "active": True, "stats": {}}]
    out = pt.backfill_party(old)
    c = out[0]
    assert c["attacks"] and c["behavior"]["profile"] in ("tatico", "feroz", "covarde", "implacavel")
    assert c["status"] == "ativo"


# test_muralha_humana_condicional_a_party removido: a passiva Muralha Humana
# (Cavaleiro da Vigília) foi substituída pelos gatilhos de Entropia das 5 Posturas
# (spec refatoracao-sistema-classes; cobertura em tests/test_classes_refactor.py).
