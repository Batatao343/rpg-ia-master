"""SPEC-298 Etapa 5 — mercador NPC, preço por relação, estoque raro, recusa."""

import copy

import pytest

from services import economy
from services import reputation as rep

MID = "ferreiro_skallgard"
MID_CURADO = "mercado_anel_dourado"


def _state(location="skallgard", race="Humano", npcs=None):
    return {
        "game_id": "g298",
        "player": {"name": "T", "race": race, "gold": 1000, "inventory": []},
        "world": {
            "current_location_id": location,
            "world_clock": {"day": 1, "period": "manha"},
            "turn_count": 1,
        },
        "world_projection": {},
        "factions": [],
        "npcs": npcs if npcs is not None else {},
    }


def _keeper(st, mid=MID):
    return rep.find_keeper(st, mid)[1]


def test_keeper_criado_sem_llm_na_primeira_visita(monkeypatch):
    import llm_setup

    monkeypatch.setattr(
        llm_setup, "get_llm", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sem LLM"))
    )
    st = _state(location="na_anel_dourado")
    mid, _stock = economy.merchant_stock(st, "na_anel_dourado")
    assert mid == MID_CURADO
    row = _keeper(st, MID_CURADO)
    assert row["name"] == "Teodora Vance" and row["race_id"] == "race_humanos"
    assert row["hidden_traits"] and 2 <= row["relationship"] <= 8
    assert row["relationship_basis"] and row["known_by_player"] is False
    # idempotente
    economy.merchant_stock(st, "na_anel_dourado")
    assert len([r for r in st["npcs"].values() if r.get("keeper_of") == MID_CURADO]) == 1


def test_keeper_grafo_brynja():
    st = _state()
    economy.merchant_stock(st, "skallgard")
    row = _keeper(st)
    assert row["id"] == "npc_brynja_forja_fria" and "Brynja" in row["name"]


def _with_keeper(rel, traits=(), race="Humano"):
    st = _state(race=race)
    economy.merchant_stock(st, "skallgard")
    key, row = rep.find_keeper(st, MID)
    st["npcs"][key] = {**row, "relationship": rel, "hidden_traits": list(traits)}
    return st


def _buy(st):
    return economy.price("pocao_cura", mode="buy", state=st, merchant=economy.MERCHANTS[MID])


def test_preco_por_faixa():
    prices = {rel: _buy(_with_keeper(rel)) for rel in (0, 2, 5, 7, 10)}
    assert prices[0] > prices[2] > prices[5] > prices[7] > prices[10]
    st = _with_keeper(5)
    keeper = _keeper(st, MID)
    assert rep.relation_price_mult(st, {**keeper, "hidden_traits": []}, "buy") == 1.0


def test_traco_comercio_ganancioso_barateia():
    from services.npc_layers import trait_dc_modifier

    st = _with_keeper(5)
    keeper = {**_keeper(st), "hidden_traits": ["ganancioso"], "revealed_traits": []}
    mod = trait_dc_modifier(keeper, "comercio")
    assert mod == -2
    assert rep.relation_price_mult(st, keeper, "buy") == pytest.approx(0.94)


def test_clamp_fator_075_150():
    st = _with_keeper(0)
    keeper = {**_keeper(st), "relationship": 0, "revealed_traits": []}
    keeper["hidden_traits"] = []
    assert rep.relation_price_mult(st, keeper, "buy") == 1.30
    leal = {**keeper, "relationship": 10}
    assert rep.relation_price_mult(st, leal, "buy") == pytest.approx(0.85)
    # fator extremo é limitado (mesmo com traço muito forte)
    monkey = {**leal, "hidden_traits": ["ganancioso"] * 20}
    assert rep.relation_price_mult(st, monkey, "buy") == rep.PRICE_FACTOR_MIN
    assert (
        rep.relation_price_mult(st, {**keeper, "hidden_traits": ["ganancioso"] * 20}, "sell") <= 1.5
    )


def test_venda_amistoso_paga_mais():
    def sell(rel):
        st = _with_keeper(rel)
        return economy.price("pocao_cura", mode="sell", state=st, merchant=economy.MERCHANTS[MID])

    assert sell(7) >= sell(5) >= sell(2)
    assert sell(10) > sell(0)


def test_preco_sem_keeper_inalterado():
    st = _state(location="skallgard")
    base = copy.deepcopy(economy.MERCHANTS[MID])
    base.pop("keeper")
    legacy = economy.price("pocao_cura", mode="buy", state=st, merchant=base)
    st2 = _with_keeper(5)
    keeper = _keeper(st2)
    st2["npcs"][keeper["name"]] = {**keeper, "hidden_traits": [], "revealed_traits": []}
    assert _buy(st2) == legacy


def test_rare_stock_so_leal(monkeypatch):
    merchant = {**economy.MERCHANTS[MID], "rare_stock": {"pocao_cura": 2}}
    monkeypatch.setitem(economy.MERCHANTS, MID, merchant)
    base = dict(merchant.get("base_stock") or {})
    base.pop("pocao_cura", None)
    st = _with_keeper(7)
    _, stock = economy.merchant_stock(st, "skallgard")
    assert "pocao_cura" not in stock
    st = _with_keeper(10)
    _, stock = economy.merchant_stock(st, "skallgard")
    assert stock.get("pocao_cura") == 2


def test_keeper_hostil_esconde_raro():
    st = _with_keeper(5)
    _, normal = economy.merchant_stock(st, "skallgard")
    assert "art_coroa_pressao_rei_anao" in normal
    st = _with_keeper(0)
    _, hidden = economy.merchant_stock(st, "skallgard")
    assert "art_coroa_pressao_rei_anao" not in hidden


def test_recusa_comercio_codigo():
    st = _state(location="na_anel_dourado", race="Anão da Fuligem")
    economy.merchant_stock(st, "na_anel_dourado")
    key, row = rep.find_keeper(st, MID_CURADO)
    # Teodora é humana (urbana, atitude 0): força um elfo hostil ao anão para o caso -2
    st["npcs"][key] = {**row, "race_id": "race_elfos", "relationship": 2}
    out = economy.execute_trade(st, "buy", "pocao_cura", 1)
    assert out["ok"] is False and out["code"] == "merchant_refuses"
    assert economy.trade_reason_code(out["reason"]) == "merchant_refuses"
    st["npcs"][key] = {**row, "race_id": "race_elfos", "relationship": 3}
    assert economy.execute_trade(st, "buy", "pocao_cura", 1).get("code") != "merchant_refuses"
