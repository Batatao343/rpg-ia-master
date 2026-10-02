"""
Fase 4.4 — Economia determinística: craft, mercadores, preços e loot tables.
Spec: specs/SPEC-014-fase-4.4-economia-deterministica.md. 100% offline.
"""
import random

import pytest

import inventory as inv
from gamedata import ARTIFACTS_DB, WORLD_MAP
from services import economy as eco


def make_state(**over):
    s = {
        "player": {"name": "T", "class_name": "Cavaleiro da Vigília", "gold": 500,
                   "inventory": [], "hp": 30, "max_hp": 30},
        "world": {"current_location_id": "skallgard", "current_location": "Skallgard",
                  "world_clock": {"day": 1, "period": "Manhã"}, "danger_level": 1},
        "world_projection": {}, "factions": [], "event_log": [],
    }
    s.update(over)
    return s


# ---------------------------------------------------------------------------
# Etapa 1 — dados/schema
# ---------------------------------------------------------------------------

def test_recipes_schema():
    assert eco.RECIPES
    for rid, r in eco.RECIPES.items():
        assert r["result_id"] in ARTIFACTS_DB, f"{rid}: result inexistente"
        for iid in r["ingredients"]:
            assert iid in ARTIFACTS_DB, f"{rid}: ingrediente {iid} inexistente"
        assert r.get("craft_tag") in ("forja", "laboratorio", "altar")


def test_merchants_schema():
    loc_ids = {l["id"] for l in WORLD_MAP["locations"]}
    assert eco.MERCHANTS
    for mid, m in eco.MERCHANTS.items():
        assert m["location_id"] in loc_ids, f"{mid}: local inexistente"
        for iid in m["base_stock"]:
            assert iid in ARTIFACTS_DB, f"{mid}: item {iid} inexistente"


def test_loot_tables_schema():
    assert "default" in eco.LOOT_TABLES
    for rid, t in eco.LOOT_TABLES.items():
        for band in ("1-2", "3-4"):
            assert t[band] and all(w > 0 for w in t[band].values()), f"{rid}/{band}"
        for rarity, pool in (t.get("pools") or {}).items():
            for iid in pool:
                assert iid in ARTIFACTS_DB, f"{rid}: pool {rarity} tem {iid} inexistente"


def test_craft_tags_no_mapa():
    tags = [t for l in WORLD_MAP["locations"] for t in (l.get("craft_tags") or [])]
    assert "forja" in tags and "laboratorio" in tags and "altar" in tags


# ---------------------------------------------------------------------------
# Etapa 2 — preços
# ---------------------------------------------------------------------------

def test_price_por_raridade_e_arredonda_5():
    s = make_state()
    p = eco.price("espada_aco_temperado", mode="buy", state=s)
    assert p % 5 == 0 and p > 0


def test_price_mod_regional_abundante():
    # minerio_ferro tem tag mineracao; skallgard idem -> 0.6
    s_sk = make_state()
    s_na = make_state(world={"current_location_id": "nova_arcadia",
                             "world_clock": {"day": 1, "period": "Manhã"}})
    assert eco.price("minerio_ferro", mode="buy", state=s_sk) < \
        eco.price("minerio_ferro", mode="buy", state=s_na)


def test_price_reputacao_hostil_sobe():
    proj = {"dynamic_edges": [{"id": "d1", "source": "clas_combate",
                               "type": "controls", "target": "skallgard",
                               "created_by_event": "e1"}]}
    hostil = make_state(world_projection=proj,
                        factions=[{"id": "clas_combate", "disposition": "hostil"}])
    neutro = make_state()
    assert eco.price("espada_aco_temperado", mode="buy", state=hostil) > \
        eco.price("espada_aco_temperado", mode="buy", state=neutro)


def test_venda_metade():
    s = make_state()
    buy = eco.price("adaga_ferro", mode="buy", state=s)
    sell = eco.price("adaga_ferro", mode="sell", state=s)
    assert sell < buy


# ---------------------------------------------------------------------------
# Etapa 3 — mercadores/estoque persistente
# ---------------------------------------------------------------------------

def test_estoque_inicializa_e_compra_esgota():
    s = make_state()
    mid, stock = eco.merchant_stock(s, "skallgard")
    assert mid == "ferreiro_skallgard"
    assert stock["espada_aco_temperado"] == 1

    out = eco.execute_trade(s, "buy", "Espada de Aço Temperado", 1)
    assert out["ok"], out
    assert inv.get_qty(out["player"]["inventory"], "espada_aco_temperado") == 1
    assert out["gold_delta"] < 0
    # esgotou
    s2 = make_state(world=out["world"])
    _, stock2 = eco.merchant_stock(s2, "skallgard")
    assert "espada_aco_temperado" not in stock2


def test_restock_por_dias():
    s = make_state()
    out = eco.execute_trade(s, "buy", "minerio de ferro", 5)
    assert out["ok"], out
    world = out["world"]
    _, stock = eco.merchant_stock(make_state(world=world), "skallgard")
    assert "minerio_ferro" not in stock
    world["world_clock"]["day"] = 10
    world = eco.restock(world)
    _, stock2 = eco.merchant_stock(make_state(world=world), "skallgard")
    assert stock2["minerio_ferro"] == 5


def test_hostil_esconde_raros():
    proj = {"dynamic_edges": [{"id": "d1", "source": "clas_combate",
                               "type": "controls", "target": "skallgard",
                               "created_by_event": "e1"}]}
    s = make_state(world_projection=proj,
                   factions=[{"id": "clas_combate", "disposition": "hostil"}])
    # incomum (rank 1) continua; se houvesse raro sumiria — valida o filtro por rank
    _, stock = eco.merchant_stock(s, "skallgard")
    ranks = [eco._RARITY_RANK.get(str(ARTIFACTS_DB[i]["rarity"]).lower(), 0) for i in stock]
    assert all(rk < 2 for rk in ranks)


def test_skallgard_diferente_nova_arcadia():
    """Critério de aceite da Fase 4."""
    s = make_state()
    _, sk = eco.merchant_stock(s, "skallgard")
    _, na = eco.merchant_stock(s, "na_anel_dourado")
    assert set(sk) != set(na)


def test_venda_sinal_do_ouro_sempre_positivo():
    s = make_state()
    s["player"]["inventory"] = inv.add_item([], "adaga_ferro", 1)
    out = eco.execute_trade(s, "sell", "adaga de ferro", 1)
    assert out["ok"] and out["gold_delta"] > 0
    assert out["player"]["gold"] == 500 + out["gold_delta"]


# ---------------------------------------------------------------------------
# Etapa 4 — craft
# ---------------------------------------------------------------------------

def test_craft_ok_consome_e_cria():
    s = make_state()
    s["player"]["inventory"] = inv.add_item(
        inv.add_item([], "espada_gasta", 1), "minerio_ferro", 2)
    out = eco.execute_craft(s, "lâmina temperada")
    assert out["ok"], out
    got = out["player"]["inventory"]
    assert inv.get_qty(got, "espada_aco_temperado") == 1
    assert inv.get_qty(got, "espada_gasta") == 0
    assert inv.get_qty(got, "minerio_ferro") == 0
    assert out["player"]["gold"] == 500 - 40


def test_craft_sem_ingrediente_falha():
    """Critério de aceite da Fase 4: craft falha sem ingrediente, com motivo."""
    s = make_state()
    s["player"]["inventory"] = inv.add_item([], "espada_gasta", 1)  # sem minério
    out = eco.execute_craft(s, "lamina_temperada")
    assert not out["ok"]
    assert "Falta ingrediente" in out["reason"]


def test_craft_local_errado_falha():
    s = make_state()
    s["world"]["current_location_id"] = "deserto_zhur"  # sem forja
    s["player"]["inventory"] = inv.add_item(
        inv.add_item([], "espada_gasta", 1), "minerio_ferro", 2)
    out = eco.execute_craft(s, "lamina temperada")
    assert not out["ok"] and "forja" in out["reason"]


# ---------------------------------------------------------------------------
# Etapa 5 — drop tables
# ---------------------------------------------------------------------------

def test_roll_loot_respeita_pesos_e_pool():
    rng = random.Random(42)
    seen = set()
    for _ in range(60):
        roll = eco.roll_loot("skallgard", 1, rng)
        assert roll["rarity"] in ("comum", "incomum")
        if roll["item_id"]:
            seen.add(roll["item_id"])
            assert roll["item_id"] in ARTIFACTS_DB
    pools = eco.LOOT_TABLES["skallgard"]["pools"]
    assert seen <= set(pools["comum"]) | set(pools["incomum"])


def test_regiao_sem_tabela_usa_default():
    roll = eco.roll_loot("regiao_fantasma", 3, random.Random(7))
    assert roll["rarity"] in ("comum", "incomum", "raro")


# ---------------------------------------------------------------------------
# Etapa 6 — loot_node reescrito (MockLLM, e2e offline)
# ---------------------------------------------------------------------------

def _node_state(loot_source, text, **over):
    from langchain_core.messages import HumanMessage
    s = make_state(**over)
    s["messages"] = [HumanMessage(content=text)]
    s["loot_source"] = loot_source
    return s


def test_buy_e2e_mock():
    from agents.loot import loot_node
    s = _node_state("SHOP", "quero comprar minerio de ferro")
    out = loot_node(s)
    assert inv.get_qty(out["player"]["inventory"], "minerio_ferro") >= 1
    assert out["player"]["gold"] < 500


def test_sell_e2e_mock():
    from agents.loot import loot_node
    s = _node_state("SHOP", "vendo minha adaga de ferro")
    s["player"]["inventory"] = inv.add_item([], "adaga_ferro", 1)
    out = loot_node(s)
    assert out["player"]["gold"] > 500  # sinal do ouro: SEMPRE Python


def test_craft_e2e_mock_sem_ingrediente():
    from agents.loot import loot_node
    s = _node_state("CRAFT", "quero forjar a lamina temperada")
    out = loot_node(s)
    # falha narrada, player intocado (sem chave 'player' no retorno de falha)
    assert "player" not in out
    assert out["messages"]


def test_treasure_usa_tabela():
    from agents.loot import loot_node
    s = _node_state("TREASURE", "abro o baú")
    out = loot_node(s)
    assert out["player"]["gold"] >= 500  # ouro nunca negativo no tesouro
    for e in out["player"]["inventory"]:
        assert e["id"] in ARTIFACTS_DB or e["id"] == inv.UNKNOWN_ID


def test_trade_intent_guard_fallback(monkeypatch):
    """FallbackLLM devolve AIMessage -> nó não estoura, usa heurística."""
    from agents import loot as loot_mod
    from langchain_core.messages import AIMessage as _AI

    class _Fallback:
        def with_structured_output(self, model):
            return self

        def invoke(self, msgs):
            return _AI(content="erro")

    monkeypatch.setattr(loot_mod, "get_llm", lambda **kw: _Fallback())
    s = _node_state("SHOP", "quero comprar corda")
    out = loot_mod.loot_node(s)
    assert out["messages"]  # não estourou
