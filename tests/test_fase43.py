"""
Fase 4.3 — Inventário estruturado, equipamento e itens usáveis em combate.
Spec: specs/SPEC-013-fase-4.3-inventario-equipamento.md. 100% offline.
"""
import copy

import pytest

import combat_mechanics as cm
import inventory as inv
from gamedata import ARTIFACTS_DB, CLASSES


def make_player(**over):
    p = {
        "name": "Testo", "class_name": "Cavaleiro da Vigília", "race": "Humano",
        "level": 1, "xp": 0, "hp": 20, "max_hp": 30,
        "mana": 5, "max_mana": 5, "stamina": 20, "max_stamina": 20,
        "gold": 10, "attributes": {"str": 14, "dex": 12, "con": 14,
                                   "int": 10, "wis": 10, "cha": 10},
        "inventory": [], "equipment": {"weapon": None, "armor": None, "accessory": None},
        "known_abilities": ["ataque_basico"], "defense": 12, "attack_bonus": 0,
        "active_conditions": [], "ability_cooldowns": {}, "pending_choices": [],
    }
    p.update(over)
    return p


# ---------------------------------------------------------------------------
# Etapa 1 — inventory.py núcleo
# ---------------------------------------------------------------------------

def test_add_stack_consumivel():
    out = inv.add_item([], "pocao_cura", 1)
    out = inv.add_item(out, "pocao_cura", 2)
    assert out == [{"id": "pocao_cura", "qty": 3}]


def test_add_nao_stackable_duplica_entrada():
    out = inv.add_item([], "espada_gasta", 1)
    out = inv.add_item(out, "espada_gasta", 1)
    assert len(out) == 2


def test_remove_decrementa_e_zera():
    out = inv.add_item([], "pocao_cura", 2)
    out, ok = inv.remove_item(out, "pocao_cura", 1)
    assert ok and inv.get_qty(out, "pocao_cura") == 1
    out, ok = inv.remove_item(out, "pocao_cura", 1)
    assert ok and out == []
    out2, ok2 = inv.remove_item(out, "pocao_cura", 1)
    assert not ok2


def test_resolve_item_name_acentos():
    assert inv.resolve_item_name("Poção de Cura Menor") == "pocao_cura"
    assert inv.resolve_item_name("poção de cura menor") == "pocao_cura"
    assert inv.resolve_item_name("pocao_cura") == "pocao_cura"
    assert inv.resolve_item_name("Coisa Inexistente XYZ") is None


def test_item_desconhecido_preserva_nome():
    out = inv.add_item([], "Relíquia Sem Registro", 1)
    assert out[0]["id"] == inv.UNKNOWN_ID
    assert out[0]["display_name"] == "Relíquia Sem Registro"
    assert inv.item_display(out[0]) == "Relíquia Sem Registro"


def test_backfill_lista_strings():
    p = make_player(inventory=["Espada Gasta", "pocao_cura", "Coisa Estranha"])
    p.pop("equipment")
    out = inv.backfill_inventory(p)
    ids = [e["id"] for e in out["inventory"]]
    assert "espada_gasta" in ids and "pocao_cura" in ids and inv.UNKNOWN_ID in ids
    # auto-equip 1x: melhor arma no slot
    assert out["equipment"]["weapon"] == "espada_gasta"


def test_backfill_idempotente():
    p = make_player(inventory=[{"id": "pocao_cura", "qty": 2}])
    out = inv.backfill_inventory(inv.backfill_inventory(p))
    assert out["inventory"] == [{"id": "pocao_cura", "qty": 2}]


# ---------------------------------------------------------------------------
# Etapa 2 — equipamento
# ---------------------------------------------------------------------------

def test_equip_slot_correto():
    p = make_player(inventory=inv.add_item([], "espada_gasta", 1))
    out, err = inv.equip(p, "espada_gasta")
    assert err is None and out["equipment"]["weapon"] == "espada_gasta"


def test_equip_tipo_errado_e_ausente():
    p = make_player(inventory=inv.add_item([], "pocao_cura", 1))
    _, err = inv.equip(p, "pocao_cura")
    assert err  # consumível não equipa
    _, err2 = inv.equip(p, "espada_gasta")
    assert err2  # não está no inventário


def test_stats_leem_so_slots():
    itens = inv.add_item(inv.add_item([], "espada_gasta", 1), "escudo_amassado", 1)
    sem_equipar = make_player(inventory=itens)
    com_espada = make_player(inventory=itens,
                             equipment={"weapon": "espada_gasta", "armor": None,
                                        "accessory": None})
    s0 = cm.compute_player_combat_stats(sem_equipar)
    s1 = cm.compute_player_combat_stats(com_espada)
    assert s1["attack"] == s0["attack"] + 1  # arma equipada conta
    # escudo no inventário mas NÃO equipado não dá AC
    assert s1["ac"] == s0["ac"]


def test_arma_inicial_da_bonus():
    """Bug histórico fechado: criador entrega arma canônica equipada com bônus."""
    from character_creator import create_player_character
    sheet = create_player_character({
        "name": "T", "class_name": "Devoto do Abismo", "race": "Humano",
        "region": "Nova Arcádia", "backstory": "", "level": "1"})
    assert sheet["equipment"]["weapon"] == "espada_gasta"
    stats = cm.compute_player_combat_stats(sheet)
    base = dict(sheet, equipment={"weapon": None, "armor": None, "accessory": None})
    assert stats["attack"] > cm.compute_player_combat_stats(base)["attack"]


def test_starting_equipment_resolve_no_db():
    for cname, c in CLASSES.items():
        for iid in c.get("starting_equipment", []) or []:
            assert iid in ARTIFACTS_DB, f"{cname}: {iid} não existe"
        # toda classe começa com pelo menos uma arma e uma poção
        tipos = [ARTIFACTS_DB[i]["type"] for i in c.get("starting_equipment", [])]
        assert "weapon" in tipos, f"{cname}: sem arma inicial"
        assert "consumable" in tipos or "potion" in tipos, f"{cname}: sem consumível"


# ---------------------------------------------------------------------------
# Etapa 4 — item usável em combate
# ---------------------------------------------------------------------------

def test_pocao_cura_em_combate(monkeypatch):
    monkeypatch.setattr(cm.random, "randint", lambda a, b: 2)
    p = make_player(hp=10, inventory=inv.add_item([], "pocao_cura", 2))
    out, logs = inv.use_item_in_combat(p, "poção")
    assert out["hp"] > 10
    assert inv.get_qty(out["inventory"], "pocao_cura") == 1
    assert any("recupera" in l for l in logs)


def test_item_fora_do_inventario_falha_gate():
    p = make_player(inventory=[])
    out, logs = inv.use_item_in_combat(p, "pocao_cura")
    assert out is p or out == p  # intocado
    assert any("Não há" in l for l in logs)


def test_item_nao_consumivel_nao_usa():
    p = make_player(inventory=inv.add_item([], "espada_gasta", 1))
    out, logs = inv.use_item_in_combat(p, "espada gasta")
    assert any("não é consumível" in l for l in logs)
    assert inv.get_qty(out.get("inventory", p["inventory"]), "espada_gasta") == 1


def test_parse_item_id_no_combate(monkeypatch):
    """Declaração estruturada de item usa consumível, gasta turno e decrementa qty."""
    from agents import combat as cbt
    from langchain_core.messages import HumanMessage
    monkeypatch.setattr(cbt, "_narrate", lambda *a, **k: "Fim.")

    p = make_player(hp=10, inventory=inv.add_item([], "pocao_cura", 1))
    p.update({"virtudes": {"forca": 2, "agilidade": 2, "corpo": 3,
                           "mente": 1, "carisma": 1},
              "vitalidade": 10, "max_vitalidade": 30,
              "ferimento_espacos": {"leve": 3, "grave": 2, "critico": 1},
              "ferimentos": {"leve": [], "grave": [], "critico": []}})
    enemy = {"id": "e1", "name": "Rato", "type": "Minion", "hp": 50, "max_hp": 50,
             "defense": 30, "status": "ativo", "attributes": {"dex": 1},
             "active_conditions": [], "attacks": [{"name": "M", "bonus": -20, "damage": "1d1"}],
             "stamina": 0, "mana": 0, "attack_mod": 0, "abilities": []}
    state = {"messages": [HumanMessage(content="bebo a poção")], "player": p,
             "enemies": [enemy], "combat": {"round": 1, "active": True},
             "combat_target": "Rato", "world": {"turn_count": 1},
             "bestiary_knowledge": {}, "pending_world_events": [],
             "combat_declaration": {
                 "actor_id": "player",
                 "acao": {"kind": "item", "item_id": "pocao_cura"}}}
    out = cbt.combat_node(state)
    assert inv.get_qty(out["player"]["inventory"], "pocao_cura") == 0


# ---------------------------------------------------------------------------
# Etapa 5 — item narrado entra no inventário (validado, nunca fantasma)
# ---------------------------------------------------------------------------

def test_items_gained_resolve(monkeypatch):
    import agents.storyteller as st

    class _FakeStoryLLM:
        def with_structured_output(self, model, *a, **k):
            self._m = model
            return self

        def invoke(self, _msgs):
            return self._m(narrative="O ferreiro te entrega uma adaga.",
                           introduced_npcs=[],
                           items_gained=["Adaga de Ferro", "Espada Flamejante do Caos"])

    monkeypatch.setattr(st, "get_llm", lambda *a, **k: _FakeStoryLLM())
    from langchain_core.messages import HumanMessage
    state = {"messages": [HumanMessage(content="aceito a adaga")],
             "player": make_player(), "world": {"turn_count": 3},
             "factions": [], "npcs": {}, "quests": [],
             "campaign_plan": {"beats": [{"description": "b", "status": "pending"}],
                               "current_step": 0, "location": "x", "climax": "y",
                               "last_planned_turn": 0},
             "world_projection": {}, "event_log": [], "pending_world_events": []}
    out = st.storyteller_node(state)
    got = out["player"]["inventory"]
    assert inv.get_qty(got, "adaga_ferro") == 1
    # item inventado NÃO entra (sem fantasma)
    assert not any(e.get("id") == inv.UNKNOWN_ID for e in got)
    rendered = out["messages"][0].content
    assert "[SISTEMA]" not in rendered
    assert "Nenhum outro objeto" in rendered
    assert out["rejected_item_claims"] == ["Espada Flamejante do Caos"]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_inventory_block_nome_canonico():
    import api as api_mod
    p = make_player(inventory=inv.add_item([], "pocao_cura", 3),
                    equipment={"weapon": None, "armor": None, "accessory": None})
    block = api_mod._inventory_block(p)
    assert block[0]["name"] == "Poção de Cura Menor"  # nome do DB, não title(id)
    assert block[0]["qty"] == 3 and block[0]["type"] == "consumable"


def test_equip_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    import api as api_mod

    p = make_player(inventory=inv.add_item([], "espada_gasta", 1))
    fake_state = {"player": p, "messages": [], "world": {}}
    saved = {}
    monkeypatch.setattr(api_mod, "load_game_state", lambda f=None: dict(fake_state))
    monkeypatch.setattr(api_mod, "save_game_state", lambda s: (saved.update(s), True)[1])
    client = TestClient(api_mod.app)

    r = client.post("/game/equip", json={"item_id": "espada_gasta"})
    assert r.status_code == 200, r.text
    assert r.json()["equipment"]["weapon"] == "espada_gasta"

    r2 = client.post("/game/equip", json={"item_id": "pocao_cura"})
    assert r2.status_code == 400
