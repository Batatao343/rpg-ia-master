"""SPEC-357 - Loja de Cartas neutras: predicado, config, prateleira, preco, compra e bloco publico."""

from __future__ import annotations

import copy
import json
import os

import pytest

import gamedata
from services import card_rewards as cr
from services import card_shop, cards, economy

BREKMAR = "brekmar"
BREKMAR_MID = "quinquilharias_brekmar"
SEM_LOJA = "ophidia"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _player(level=4, gold=500, **extra):
    p = {
        "class_name": "Sangromante",
        "level": level,
        "known_cards": [],
        "prepared_cards": [],
        "deck": [],
        "gold": gold,
    }
    p.update(extra)
    return p


def _state(loc=BREKMAR, day=1, level=4, gold=500, **player):
    return {
        "game_id": "g357",
        "player": _player(level=level, gold=gold, **player),
        "world": {"current_location_id": loc, "world_clock": {"day": day}, "danger_level": 1},
    }


def _load(name):
    with open(os.path.join(gamedata.DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- Etapa 1
def test_is_neutral_matches_rewards_pool():
    allc = cards.all_cards()
    neu = [c for cid, c in allc.items() if cid.startswith("neu1_")]
    assert len(neu) == 40 and all(cards.is_neutral(c) for c in neu)
    for c in allc.values():
        if c.get("classe") not in ("", "Neutra", "neutra", None) and not c.get("neutra"):
            assert not cards.is_neutral(c)
    assert not cards.is_neutral(None)


def test_loja_config_valid():
    cfg = _load("cards/_loja.json")
    merchants = _load("merchants.json")
    regions = {loc.get("region_id") for loc in _load("world_map.json")["locations"]}
    allc = cards.all_cards()
    for mid, row in cfg["mercadores"].items():
        assert mid in merchants
        for r in row["regioes"]:
            assert r in regions, r
        for pat in row.get("excluir") or []:
            assert any(cid == pat or (pat.endswith("_") and cid.startswith(pat)) for cid in allc)
    prices = cfg["preco_raridade"]
    assert "abissal" not in prices
    assert all(isinstance(v, int) and v > 0 for v in prices.values())
    assert prices["comum"] < prices["incomum"] < prices["rara"]
    assert cfg["preco_por_tier"] > 0 and cfg["prateleira"] > 0


def test_rewards_roll_unchanged():
    """R15: o predicado extraido nao muda o pool neutro do espolio; o sorteio segue deterministico."""
    st = _state(level=12)
    player = st["player"]
    legacy = sorted(
        cid
        for cid, c in cards.all_cards().items()
        if (c.get("classe") in ("", "Neutra", "neutra", None) or c.get("neutra"))
        and not c.get("regiao_exclusiva")
        and cr._eligible(c, player, boss=False)
        and (not c.get("regiao") or str(c.get("regiao")) in {BREKMAR})
    )
    pools = cr._pools(player, [], boss=False, region_ids={BREKMAR})
    assert pools["neutra"] == legacy
    for seed in range(20):
        assert cr.roll_rewards(st, None, seed) == cr.roll_rewards(copy.deepcopy(st), None, seed)


# ---------------------------------------------------------------- Etapa 2
def test_shelf_deterministic():
    st = _state()
    assert card_shop.shelf(st) == card_shop.shelf(copy.deepcopy(st))
    mid, ids = card_shop.shelf(st)
    assert mid == BREKMAR_MID and len(ids) == 3


def test_shelf_rotates_by_restock_epoch():
    shelves = {tuple(card_shop.shelf(_state(day=3 * e, level=12))[1]) for e in range(1, 11)}
    assert len(shelves) >= 2
    assert card_shop.shelf(_state(day=6)) == card_shop.shelf(_state(day=8))  # mesma epoca


def test_shelf_respects_region_and_generals():
    allc = cards.all_cards()
    _, sk = card_shop.shelf(_state(loc="skallgard", level=12))
    assert sk and all(allc[c].get("regiao") == "skallgard" for c in sk)
    pool_p = card_shop.shelf_pool(_state(loc="pantano_melancolia", level=12), "curandeira_pantano")
    assert pool_p and all(not allc[c].get("regiao") for c in pool_p)
    pool_br = card_shop.shelf_pool(_state(level=12), BREKMAR_MID)
    assert pool_br and not any(c.startswith("neu1_ka_") for c in pool_br)
    assert any(allc[c].get("regiao") == "brekmar" for c in pool_br)


def test_shelf_never_abissal_or_over_level():
    allc = cards.all_cards()
    for lvl in (1, 4, 9, 20):
        for cid in card_shop.shelf_pool(_state(level=lvl), BREKMAR_MID):
            assert cr.rarity_of(allc[cid]) != "abissal"
            assert int(allc[cid].get("level_req", 1)) <= lvl
    assert card_shop.shelf_pool(_state(level=1), BREKMAR_MID)


def test_known_card_stays_marked():
    st = _state(gold=9999)
    _, ids = card_shop.shelf(st)
    assert card_shop.buy(st, ids[0])["ok"]
    assert card_shop.shelf(st)[1] == ids
    shop = card_shop.public_shop(st)
    assert [o["conhecida"] for o in shop["ofertas"]] == [True, False, False]


def test_hostile_hides_rare(monkeypatch):
    st = _state(loc="skallgard", level=12)
    assert any(
        cr.rarity_of(cards.get_card(c)) == "rara"
        for c in card_shop.shelf_pool(st, "ferreiro_skallgard")
    )
    monkeypatch.setattr(economy, "_controller_disposition", lambda s, loc: "hostil")
    pool = card_shop.shelf_pool(st, "ferreiro_skallgard")
    assert pool and all(cr.rarity_of(cards.get_card(c)) != "rara" for c in pool)


def test_closed_merchant_no_shelf(monkeypatch):
    from services import location_states

    real = location_states.location_effects
    monkeypatch.setattr(
        location_states,
        "location_effects",
        lambda s, loc: {**real(s, loc), "merchant_closed": True},
    )
    assert card_shop.shelf(_state())[1] == []
    assert card_shop.public_shop(_state()) is None


def test_no_config_no_cards():
    assert card_shop.shelf_pool(_state(), "mercador_inexistente") == []
    assert card_shop.shelf(_state(loc=SEM_LOJA))[1] == []


def test_card_price_formula(monkeypatch):
    st = _state()
    merchant = economy.MERCHANTS[BREKMAR_MID]
    mult = economy.local_buy_mult(st, merchant)
    cfg = card_shop._config()
    allc = cards.all_cards()
    com = next(c for c in allc.values() if c["id"].startswith("neu1_br_") and c.get("tier") == 1)
    assert card_shop.card_price(st, com["id"], merchant) == economy._round5(
        cfg["preco_raridade"]["comum"] * mult
    )
    inc = next(
        c for c in allc.values() if c["id"].startswith("neu1_") and cr.rarity_of(c) == "incomum"
    )
    base = cfg["preco_raridade"]["incomum"] + cfg["preco_por_tier"] * (int(inc["tier"]) - 1)
    assert card_shop.card_price(st, inc["id"], merchant) == economy._round5(base * mult)
    normal = card_shop.card_price(st, com["id"], merchant)
    monkeypatch.setattr(economy, "_controller_disposition", lambda s, loc: "hostil")
    hostile = card_shop.card_price(st, com["id"], merchant)
    expected = economy._round5(cfg["preco_raridade"]["comum"] * mult * economy.HOSTILE_BUY_MULT)
    assert hostile == expected and hostile > normal


def test_local_buy_mult_matches_item_price():
    st = _state()
    merchant = economy.MERCHANTS[BREKMAR_MID]
    item = next(iter(merchant["base_stock"]))
    supply = economy._supply_factor_for(item, st)["mult"]
    # price() = base x oferta x fatores locais (mesma ordem): local_buy_mult e o produto dos locais
    p = float(economy.base_price(item)) * supply
    for f in economy._local_factors(st, "buy", merchant):
        p *= f["mult"]
    assert economy._round5(p) == economy.price(item, mode="buy", state=st, merchant=merchant)
    prod = economy.local_buy_mult(st, merchant)
    assert abs(economy.base_price(item) * supply * prod - p) < 1e-6


# ---------------------------------------------------------------- Etapa 3
def test_buy_debits_and_adds_to_deck():
    st = _state()
    st["player"]["deck"] = list(cards.basicas_for_class("Sangromante")["golpe"][:1]) * 12
    _, ids = card_shop.shelf(st)
    price = card_shop.card_price(st, ids[0], economy.MERCHANTS[BREKMAR_MID])
    res = card_shop.buy(st, ids[0])
    assert res["ok"] and res["gold"] == price and res["destino"] == "baralho"
    assert st["player"]["gold"] == 500 - price
    assert ids[0] in st["player"]["known_cards"] and ids[0] in st["player"]["deck"]


def test_buy_deck_full_goes_to_acervo():
    st = _state()
    st["player"]["deck"] = ["x"] * cards.DECK_MAX
    _, ids = card_shop.shelf(st)
    res = card_shop.buy(st, ids[0])
    assert res["ok"] and res["destino"] == "acervo"
    assert ids[0] in st["player"]["known_cards"] and ids[0] not in st["player"]["deck"]


def test_buy_refuses_known_off_shelf_low_gold_level_in_conflict():
    st = _state()
    _, ids = card_shop.shelf(st)
    st["player"]["known_cards"] = [ids[0]]
    assert "conhece" in card_shop.buy(st, ids[0])["error"]
    off = next(c for c in cards.all_cards() if c.startswith("neu1_ka_"))  # Kahen: fora da loja
    assert "não está à venda" in card_shop.buy(st, off)["error"]
    st["player"]["gold"] = 1
    low = card_shop.buy(st, ids[1])
    assert not low["ok"] and "Faltam" in low["error"] and st["player"]["gold"] == 1
    st2 = _state(gold=500)
    st2["combat"] = {"active": True}
    res = card_shop.buy(st2, ids[0])
    assert not res["ok"] and res["conflito"] is True and st2["player"]["gold"] == 500


def test_buy_refuses_card_above_level():
    st = _state(level=12, gold=9999)
    _, ids = card_shop.shelf(st)
    st["player"]["level"] = 1  # nivel caiu entre a prateleira e o clique: nada e vendido
    pick = next(i for i in ids if int(cards.get_card(i).get("level_req", 1)) > 1)
    res = card_shop.buy(st, pick)
    assert not res["ok"] and st["player"]["gold"] == 9999


def test_buy_off_flag(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    st = _state()
    _, ids = card_shop.shelf(st)
    res = card_shop.buy(st, ids[0])
    assert not res["ok"] and st["player"]["gold"] == 500
    assert card_shop.public_shop(st) is None


def test_buy_keeper_refuses(monkeypatch):
    st = _state()
    _, ids = card_shop.shelf(st)
    monkeypatch.setattr(
        economy, "_keeper_refusal", lambda s, m, mer: {"ok": False, "reason": "Okka recusa."}
    )
    res = card_shop.buy(st, ids[0])
    assert not res["ok"] and "recusa" in res["error"] and st["player"]["gold"] == 500
    shop = card_shop.public_shop(st)
    assert shop["motivo"] == "Okka recusa." and all(o["bloqueio"] for o in shop["ofertas"])


def test_public_shop_pure():
    st = _state()
    before = copy.deepcopy(st)
    shop = card_shop.public_shop(st)
    assert st == before
    assert shop["merchant_id"] == BREKMAR_MID and len(shop["ofertas"]) == 3
    assert 1 <= shop["renova_em_dias"] <= 3


def test_public_shop_bloqueio_texts():
    st = _state(gold=10)
    st["player"]["known_cards"] = [card_shop.shelf(st)[1][0]]
    shop = card_shop.public_shop(st)
    first, second = shop["ofertas"][0], shop["ofertas"][1]
    assert first["bloqueio"] == "Você já conhece essa Carta."
    assert second["bloqueio"] == f"Faltam {second['preco'] - 10} de ouro."
    rich = card_shop.public_shop(_state())
    assert all(
        o["bloqueio"] is None and o["destino"] in ("baralho", "acervo", "preparadas")
        for o in rich["ofertas"]
    )


def test_public_shop_none_in_combat_or_without_merchant():
    st = _state()
    st["combat"] = {"active": True}
    assert card_shop.public_shop(st) is None
    assert card_shop.public_shop(_state(loc=SEM_LOJA)) is None


def test_buy_telemetry_source_loja(monkeypatch):
    seen = []
    tel = card_shop.card_telemetry
    monkeypatch.setattr(tel, "picked", lambda cid: seen.append((cid, tel._source.get())))
    st = _state()
    _, ids = card_shop.shelf(st)
    card_shop.buy(st, ids[0])
    assert seen == [(ids[0], "loja")]


def test_is_neutral_defined_once():
    """P2-3: guarda contra definicao duplicada apos rebase com a SPEC-355."""
    src = open(os.path.join(os.path.dirname(cards.__file__), "cards.py"), encoding="utf-8").read()
    assert src.count("def is_neutral(") == 1
