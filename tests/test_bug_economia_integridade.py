"""SPEC-227 — integridade de economia/inventário (venda, craft, equipamento, únicos)."""
import copy
import random

import pytest

import combat_mechanics as cm
import inventory as inv
from services import economy as eco

LOC = "na_anel_dourado"          # mercado_anel_dourado
UNIQ = "art_adaga_vidro_dragao"


def _state(gold=100, inventory=None, equipment=None, loc=LOC, **p):
    player = {"name": "T", "gold": gold, "inventory": inventory or [],
              "equipment": equipment or {"weapon": None, "armor": None, "accessory": None},
              "hp": 30, "max_hp": 30, **p}
    return {"world": {"turn_count": 1, "current_location_id": loc,
                      "world_clock": {"day": 1, "period": "Manhã"}},
            "world_projection": {}, "event_log": [], "pending_world_events": [],
            "player": player}


def test_remove_item_consumes_across_entries():
    items = [{"id": "adaga_ferro", "qty": 1}, {"id": "adaga_ferro", "qty": 1}]
    out, ok = inv.remove_item(items, "adaga_ferro", 2)
    assert ok and out == []
    snapshot = copy.deepcopy(items)
    out, ok = inv.remove_item(items, "adaga_ferro", 3)
    assert not ok and out == snapshot and items == snapshot


def test_sell_two_unstackable_separate_entries_removes_both():
    items = [{"id": "adaga_ferro", "qty": 1}, {"id": "adaga_ferro", "qty": 1}]
    out = eco.execute_trade(_state(inventory=items), "sell", "adaga_ferro", 2)
    assert out["ok"], out
    assert out["gold_delta"] > 0
    assert out["player"]["inventory"] == []


def test_sell_aborts_when_removal_fails(monkeypatch):
    monkeypatch.setattr(eco, "remove_item", lambda i, *a, **k: (i, False))
    st = _state(inventory=[{"id": "adaga_ferro", "qty": 1}])
    out = eco.execute_trade(st, "sell", "adaga_ferro", 1)
    assert not out["ok"]
    assert st["player"]["gold"] == 100


def test_sell_without_merchant_refused():
    st = _state(inventory=[{"id": "adaga_ferro", "qty": 1}], loc="__nowhere__")
    out = eco.execute_trade(st, "sell", "adaga_ferro", 1)
    assert not out["ok"]
    assert "mercador" in out["reason"]


def test_sold_item_is_unequipped():
    st = _state(inventory=[{"id": "adaga_ferro", "qty": 1}],
                equipment={"weapon": "adaga_ferro", "armor": None, "accessory": None})
    out = eco.execute_trade(st, "sell", "adaga_ferro", 1)
    assert out["ok"]
    assert out["player"]["equipment"]["weapon"] is None
    assert out["unequipped"] == ["weapon"]


def test_combat_ignores_slot_without_possession():
    p = {"name": "T", "class_name": "Sangromante", "level": 1, "inventory": [],
         "virtudes": {}, "equipment": {"weapon": UNIQ, "armor": None, "accessory": None}}
    assert cm.equipped_ids(p) == []
    p["inventory"] = [{"id": UNIQ, "qty": 1}]
    assert cm.equipped_ids(p) == [UNIQ]


def test_restock_keeps_unique_held_by_merchant():
    st = _state(inventory=[{"id": UNIQ, "qty": 1}])
    out = eco.execute_trade(st, "sell", UNIQ, 1)
    assert out["ok"], out
    world = out["world"]
    # projeção mínima: o mercador segura o único
    proj = {"unique_items": {UNIQ: {"holder": "mercado_anel_dourado"}}}
    world["world_clock"] = {"day": 4, "period": "Manhã"}
    eco.restock(world, projection=proj)
    assert world["merchant_stocks"]["mercado_anel_dourado"].get(UNIQ) == 1


def test_sell_free_item_removes_correct_entry():
    items = [{"id": inv.UNKNOWN_ID, "qty": 1, "display_name": "Amuleto da Avó"},
             {"id": inv.UNKNOWN_ID, "qty": 1, "display_name": "Pedra Lisa"}]
    ent = inv.find_entry_in_inventory(items, "Pedra Lisa")
    assert ent["display_name"] == "Pedra Lisa"
    out, ok = inv.remove_item(items, ent["id"], 1, display_name=ent["display_name"])
    assert ok and [e["display_name"] for e in out] == ["Amuleto da Avó"]
    # D-A: item livre não é vendável
    res = eco.execute_trade(_state(inventory=items), "sell", "Pedra Lisa", 1)
    assert not res["ok"] and "valor de mercado" in res["reason"]


def test_potion_full_hp_not_consumed():
    p = {"name": "T", "hp": 30, "max_hp": 30, "inventory": inv.add_item([], "pocao_cura", 1),
         "equipment": {}, "active_conditions": []}
    out, logs = inv.use_item_in_combat(p, "pocao_cura")
    assert inv.get_qty(out["inventory"], "pocao_cura") == 1
    res = inv.try_use_item(p, "pocao_cura")
    assert not res["ok"] and res["consumed_turn"] is False
    assert "cheia" in res["reason"]


def test_hostile_consumable_without_target_not_consumed():
    p = {"name": "T", "hp": 10, "max_hp": 30,
         "inventory": inv.add_item([], "bomba_de_trovao", 1), "active_conditions": []}
    res = inv.try_use_item(p, "bomba_de_trovao", None)
    assert not res["ok"]
    assert inv.get_qty(res["player"]["inventory"], "bomba_de_trovao") == 1


def test_create_level_20_respects_entropy_cap():
    from character_creator import create_player_character
    import progression
    from gamedata import CLASSES
    sheet = create_player_character(
        {"name": "A", "class_name": "Devoto do Abismo", "race": "Humano",
         "region": "Nova Arcádia", "level": 20}, use_llm_flavor=False)
    cap = CLASSES["Devoto do Abismo"]["late_entropy_curve"]["cap"]
    assert sheet["level"] == 20
    assert sheet["max_entropy"] == cap
    assert sheet["pending_choices"] == []
    assert sheet["known_cards"]


def test_flavor_inventory_never_resolves_unique():
    entry = inv.resolve_flavor_item("Adaga de Vidro-Dragão")
    assert entry["id"] == inv.UNKNOWN_ID
    assert entry["display_name"] == "Adaga de Vidro-Dragão"
    assert inv.resolve_flavor_item("Adaga de Ferro")["id"] == "adaga_ferro"


def test_reconcile_equipment_pure():
    p = {"inventory": [], "equipment": {"weapon": "adaga_ferro", "armor": None}}
    out, removed = inv.reconcile_equipment(p)
    assert removed == ["weapon"] and out["equipment"]["weapon"] is None
    assert p["equipment"]["weapon"] == "adaga_ferro"


def test_gold_never_negative_property():
    rng = random.Random(7)
    st = _state(gold=60, inventory=[{"id": "adaga_ferro", "qty": 1}])
    for _ in range(200):
        mode = rng.choice(["buy", "sell", "craft"])
        ref = rng.choice(["adaga_ferro", "pocao_cura", "corda", "lamina temperada"])
        if mode == "craft":
            out = eco.execute_craft(st, ref)
        else:
            out = eco.execute_trade(st, mode, ref, rng.randint(1, 3))
        if out.get("ok"):
            st = {**st, "player": out["player"], "world": out["world"]}
        assert int(st["player"]["gold"]) >= 0


def test_load_reconciles_orphan_equipment(tmp_path):
    import persistence
    raw = {"game_id": "g", "player": {
        "name": "T", "gold": 7, "inventory": [],
        "equipment": {"weapon": "adaga_ferro", "armor": None, "accessory": None}}}
    state = persistence._raw_to_state(raw)
    assert state["player"]["equipment"]["weapon"] is None
    assert state["player"]["gold"] == 7
    again = persistence._raw_to_state({**raw, "player": state["player"]})
    assert again["player"] == state["player"]


def test_refused_item_does_not_spend_round():
    """R8 em combate: poção recusada (Vitalidade cheia) não gasta a Ação nem dá
    turno aos inimigos."""
    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs
    from services import conflict_turn as ct
    player = orch.ensure_combat_sheet(
        {"id": "player", "name": "H", "is_player": True, "class_name": "Sangromante",
         "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
         "attack_formula": "2d6", "entropy": 10, "max_entropy": 10, "abyss_charge": 0,
         "inventory": inv.add_item([], "pocao_cura", 1)}, is_player=True)
    gob = orch.ensure_combat_sheet({"id": "gob_1", "name": "Goblin", "type": "Minion",
                                    "hp": 12, "max_hp": 12, "ac": 11,
                                    "attributes": {"str": 10, "dex": 12, "con": 10,
                                                   "int": 8, "wis": 8, "cha": 6}})
    scene = cs.new_scene()
    for i in ("player", "gob_1"):
        cs.place(scene, i)
    cs.freeze(scene)
    decl = ct.TurnDeclaration(actor_id="player",
                              acao=ct.TurnStep(kind="item", item_id="pocao_cura"))
    out = orch.run_round(scene, {"player": player, "gob_1": gob},
                         {"hero": ["player"], "enemy": ["gob_1"]}, {"player": player},
                         declarations={"player": decl}, rng=random.Random(1))
    assert out["resolved_turns"] == [] and out.get("action_refused") is True
    assert inv.get_qty(player["inventory"], "pocao_cura") == 1
    assert not out["attacks"]
    assert any("cheia" in line for line in out["logs"])


def test_negative_gold_clamp_logs(caplog):
    import logging
    st = _state(gold=0, inventory=[])
    with caplog.at_level(logging.WARNING):
        assert eco.clamp_gold(st["player"], -5) == 0
    assert "economy.negative_gold_prevented" in caplog.text


def test_restock_preserved_unique_can_be_rebought():
    st = _state(inventory=[{"id": UNIQ, "qty": 1}])
    sold = eco.execute_trade(st, "sell", UNIQ, 1)
    proj = {"unique_items": {UNIQ: {"holder": "mercado_anel_dourado"}}}
    world = sold["world"]
    world["world_clock"] = {"day": 4, "period": "Manhã"}
    eco.restock(world, projection=proj)
    rebuy = {**st, "world": world, "world_projection": proj,
             "player": {**sold["player"], "gold": 99999}}
    out = eco.execute_trade(rebuy, "buy", UNIQ, 1)
    assert out["ok"], out
    assert inv.get_qty(out["player"]["inventory"], UNIQ) == 1
