"""SPEC-311 Etapa 2 — preço com motivo (R10-R16).

A matriz de caracterização foi escrita e gravada ANTES da refatoração de `price()`
(R10): os inteiros esperados vieram do código anterior e não podem mudar.
"""

from __future__ import annotations

import math
import re

import pytest

from services import economy

_ENG = {"RPG_WORLD_ENGINE": "on", "RPG_CALENDAR": "on"}


@pytest.fixture(autouse=True)
def _engine_on(monkeypatch):
    for k, v in _ENG.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------------------
# Construtores de cenário (compartilhados pela matriz de caracterização)
# ---------------------------------------------------------------------------
def _base_state(loc: str) -> dict:
    import gamedata

    return {
        "game_id": "g311",
        "player": {"name": "T", "race": "Humano", "gold": 1000, "inventory": []},
        "world": {
            "current_location_id": loc,
            "current_location": loc,
            "world_clock": {"day": 5, "period": "Manhã"},
            "turn_count": 3,
            "visited": [loc],
        },
        "world_projection": {},
        "factions": gamedata.seed_factions(),
        "faction_intel": {},
        "faction_membership": {},
        "quests": [],
        "npcs": {},
        "event_log": [],
    }


def _with_state(st: dict, name: str, sev: int, **extra) -> dict:
    loc = st["world"]["current_location_id"]
    st["world_projection"] = {"location_states": {loc: {"state": name, "severity": sev, **extra}}}
    return st


def _block_routes(st: dict) -> dict:
    import gamedata

    loc = st["world"]["current_location_id"]
    conns = (gamedata.get_location(loc) or {}).get("connections") or []
    st["world_projection"] = {"blocked_routes": [{"a": loc, "b": c} for c in conns]}
    return st


def _closed_pass(st: dict) -> dict:
    st["world"]["season"] = {"id": "inverno", "label": "inverno", "day_in_season": 1}
    return st


def _keeper(st: dict, mid: str, rel: int) -> dict:
    m = economy.MERCHANTS[mid]
    npcs = economy._persist_keeper(st, mid, m)
    if npcs is not None:
        st["npcs"] = npcs
    from services import reputation as rep

    key, row = rep.find_keeper(st, mid)
    if key is not None:
        st["npcs"][key] = {**row, "relationship": rel}
    return st


def _member(st: dict) -> dict:
    from tests.spec301_support import joined

    out = joined(st, "legiao_ferro", rank_index=2)
    return out


SCENARIOS = {
    "plain": lambda st, mid: st,
    "cerco1": lambda st, mid: _with_state(st, "cerco", 1),
    "cerco2": lambda st, mid: _with_state(st, "cerco", 2),
    "cerco3": lambda st, mid: _with_state(st, "cerco", 3),
    "festa": lambda st, mid: _with_state(st, "festa", 1, festival_id="dia_da_fundacao"),
    "rota_bloqueada": lambda st, mid: _block_routes(st),
    "passo_fechado": lambda st, mid: _closed_pass(st),
    "keeper_hostil": lambda st, mid: _keeper(st, mid, 0),
    "keeper_leal": lambda st, mid: _keeper(st, mid, 10),
    "patente": lambda st, mid: _member(st),
}


def _items(mid: str) -> list[str]:
    stock = list(economy.MERCHANTS[mid].get("base_stock") or {})[:3]
    # itens caros afinam a sensibilidade ao arredondamento de 5 em 5
    extra = ["espada_aco_temperado", "art_coroa_pressao_rei_anao"]
    return stock + [i for i in extra if i not in stock]


def _matrix(monkeypatch) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for name, build in SCENARIOS.items():
        row: list[int] = []
        for mid in sorted(economy.MERCHANTS):
            m = economy.MERCHANTS[mid]
            for hostile in (False, True):
                if hostile and name not in ("plain", "cerco2"):
                    continue
                monkeypatch.setattr(
                    economy,
                    "_controller_disposition",
                    lambda state, loc, _h=hostile: "hostil" if _h else "neutro",
                )
                st = build(_base_state(m["location_id"]), mid)
                for iid in _items(mid):
                    for mode in ("buy", "sell"):
                        row.append(economy.price(iid, mode=mode, state=st, merchant=m))
        out[name] = row
    return out


# fmt: off
EXPECTED: dict[str, list[int]] = {
    "plain": [
        10, 5, 10, 5, 10, 5, 115, 60, 1455, 775, 10, 5, 10, 5, 15, 5, 175, 60, 2180, 775,
        50, 25, 5, 1, 15, 10, 120, 60, 1500, 750, 75, 25, 10, 1, 20, 10, 180, 60, 2250, 750,
        5, 1, 5, 1, 95, 45, 125, 60, 1545, 730, 5, 1, 5, 1, 140, 45, 185, 60, 2320, 730,
        140, 60, 115, 50, 5, 1, 1750, 780, 210, 60, 175, 50, 10, 1, 2625, 780, 60, 30, 10,
        5, 10, 5, 140, 75, 1745, 930, 85, 30, 15, 5, 15, 5, 210, 75, 2620, 930, 1, 1, 5, 5,
        5, 5, 110, 55, 1350, 675, 1, 1, 10, 5, 10, 5, 160, 55, 2025, 675,
    ],
    "cerco1": [
        10, 5, 10, 5, 15, 5, 175, 60, 2180, 775, 75, 25, 10, 1, 20, 10, 180, 60, 2250, 750,
        5, 1, 5, 1, 140, 45, 185, 60, 2320, 730, 210, 60, 175, 50, 10, 1, 2625, 780, 85, 30,
        15, 5, 15, 5, 210, 75, 2620, 930, 1, 1, 10, 5, 10, 5, 160, 55, 2025, 675,
    ],
    "cerco2": [
        15, 5, 15, 5, 15, 5, 210, 60, 2620, 775, 20, 5, 20, 5, 25, 5, 315, 60, 3930, 775,
        90, 25, 10, 1, 25, 10, 215, 60, 2700, 750, 135, 25, 15, 1, 40, 10, 325, 60, 4050,
        750, 5, 1, 5, 1, 165, 45, 220, 60, 2780, 730, 10, 1, 10, 1, 250, 45, 335, 60, 4170,
        730, 250, 60, 210, 50, 10, 1, 3150, 780, 380, 60, 315, 50, 15, 1, 4720, 780, 105,
        30, 20, 5, 20, 5, 250, 75, 3145, 930, 155, 30, 30, 5, 30, 5, 375, 75, 4715, 930, 1,
        1, 15, 5, 15, 5, 195, 55, 2430, 675, 1, 1, 20, 5, 20, 5, 290, 55, 3645, 675,
    ],
    "cerco3": [
        15, 5, 15, 5, 20, 5, 255, 60, 3200, 775, 110, 25, 10, 1, 35, 10, 265, 60, 3300, 750,
        5, 1, 10, 1, 205, 45, 270, 60, 3400, 730, 310, 60, 255, 50, 10, 1, 3850, 780, 130,
        30, 25, 5, 25, 5, 305, 75, 3840, 930, 1, 1, 15, 5, 15, 5, 240, 55, 2970, 675,
    ],
    "festa": [
        10, 5, 10, 5, 10, 5, 130, 60, 1600, 775, 55, 25, 5, 1, 15, 10, 130, 60, 1650, 750,
        5, 1, 5, 1, 100, 45, 135, 60, 1700, 730, 155, 60, 130, 50, 5, 1, 1925, 780, 65, 30,
        15, 5, 15, 5, 155, 75, 1920, 930, 1, 1, 10, 5, 10, 5, 120, 55, 1485, 675,
    ],
    "rota_bloqueada": [
        10, 5, 10, 5, 10, 5, 115, 60, 1455, 775, 90, 45, 10, 5, 15, 10, 120, 60, 1500, 750,
        5, 1, 5, 1, 95, 45, 125, 60, 1545, 730, 140, 60, 115, 50, 5, 1, 1750, 780, 105, 55,
        10, 5, 10, 5, 140, 75, 1745, 930, 1, 1, 15, 5, 5, 5, 110, 55, 1350, 675,
    ],
    "passo_fechado": [
        10, 5, 10, 5, 10, 5, 115, 60, 1455, 775, 50, 25, 5, 1, 15, 10, 120, 60, 1500, 750,
        5, 1, 5, 1, 95, 45, 125, 60, 1545, 730, 140, 60, 115, 50, 5, 1, 1750, 780, 60, 30,
        10, 5, 10, 5, 140, 75, 1745, 930, 1, 1, 5, 5, 5, 5, 110, 55, 1350, 675,
    ],
    "keeper_hostil": [
        10, 5, 10, 5, 15, 5, 150, 50, 1890, 595, 65, 20, 5, 1, 20, 5, 155, 45, 1950, 575, 5,
        1, 5, 1, 120, 35, 160, 45, 2010, 560, 180, 50, 150, 40, 5, 1, 2275, 620, 75, 25, 15,
        5, 15, 5, 180, 55, 2270, 715, 1, 1, 10, 5, 10, 5, 140, 40, 1755, 520,
    ],
    "keeper_leal": [
        5, 5, 5, 5, 10, 5, 100, 75, 1235, 910, 40, 30, 5, 5, 15, 10, 100, 70, 1275, 880, 5,
        1, 5, 1, 80, 50, 105, 70, 1315, 855, 120, 75, 100, 60, 5, 5, 1485, 915, 50, 35, 10,
        5, 10, 5, 120, 85, 1485, 1090, 1, 1, 5, 5, 5, 5, 90, 65, 1150, 795,
    ],
    "patente": [
        10, 5, 10, 5, 10, 5, 115, 60, 1455, 775, 45, 25, 5, 1, 15, 10, 110, 60, 1350, 750,
        5, 1, 5, 1, 95, 45, 125, 60, 1545, 730, 140, 60, 115, 50, 5, 1, 1750, 780, 60, 30,
        10, 5, 10, 5, 140, 75, 1745, 930, 1, 1, 5, 5, 5, 5, 110, 55, 1350, 675,
    ],
}
# fmt: on


def test_price_characterization_matrix(monkeypatch):
    """R10: a refatoração sobre `price_factors` não muda nenhum preço."""
    got = _matrix(monkeypatch)
    assert got.keys() == EXPECTED.keys()
    for name in EXPECTED:
        assert got[name] == EXPECTED[name], name
    # a matriz precisa ser sensível: cenários diferentes dão preços diferentes
    assert len({tuple(v) for v in EXPECTED.values()}) >= 8


# ---------------------------------------------------------------------------
# R10-R16 — fatores, motivos, loot e NPC-mercador
# ---------------------------------------------------------------------------
def _round5(v: float) -> int:
    return max(1, int(round(v / 5.0) * 5))


def _merchant_state(mid: str, scenario: str = "plain") -> tuple[dict, dict]:
    m = economy.MERCHANTS[mid]
    return SCENARIOS[scenario](_base_state(m["location_id"]), mid), m


def test_price_equals_product_of_factors():
    """R10: `price()` é a base vezes o produto dos fatores (na mesma ordem)."""
    for name in SCENARIOS:
        for mid in sorted(economy.MERCHANTS):
            st, m = _merchant_state(mid, name)
            for iid in _items(mid):
                for mode in ("buy", "sell"):
                    p = float(economy.base_price(iid))
                    for f in economy.price_factors(iid, mode=mode, state=st, merchant=m):
                        p *= f["mult"]
                    assert economy.price(iid, mode=mode, state=st, merchant=m) == _round5(p)


def test_price_factors_codes_and_order():
    st, m = _merchant_state("ferreiro_skallgard", "cerco2")
    codes = [
        f["code"] for f in economy.price_factors("pocao_cura", mode="buy", state=st, merchant=m)
    ]
    assert codes[:2] == ["supply_rota", "mercador"]
    assert codes[-1] == "estado_local"
    sell = economy.price_factors("pocao_cura", mode="sell", state=st, merchant=m)
    assert sell[-1] == {"code": "venda", "mult": economy.SELL_FACTOR}


def _all_texts() -> list[str]:
    out: list[str] = []
    for name in SCENARIOS:
        for mid in sorted(economy.MERCHANTS):
            st, m = _merchant_state(mid, name)
            for mode in ("buy", "sell"):
                for iid in (None, *_items(mid)):
                    out += [
                        r["text"]
                        for r in economy.price_reasons(st, mode=mode, item_id=iid, merchant=m)
                    ]
    return out


def test_price_reasons_threshold_and_cap(monkeypatch):
    """R11: limiar 0,05, teto 3, ordem por |log(mult)| e depois por code."""
    monkeypatch.setattr(economy, "_controller_disposition", lambda s, loc: "hostil")
    st, m = _merchant_state("ferreiro_skallgard", "cerco3")
    reasons = economy.price_reasons(st, mode="buy", item_id="pocao_cura", merchant=m)
    assert 1 <= len(reasons) <= economy.REASONS_MAX
    factors = {
        f["code"]: f["mult"]
        for f in economy.price_factors("pocao_cura", mode="buy", state=st, merchant=m)
    }
    mags = [abs(math.log(factors[r["code"]])) for r in reasons]
    assert mags == sorted(mags, reverse=True)
    assert reasons[0]["code"] == "estado_local"  # cerco 3 (x2,2) domina
    # fator abaixo do limiar nunca vira motivo
    soft = {**m, "price_mult": 1.04}
    st2, _ = _merchant_state("ferreiro_skallgard", "plain")
    assert all(
        r["code"] != "mercador"
        for r in economy.price_reasons(st2, mode="buy", item_id="pocao_cura", merchant=soft)
    )
    # SELL_FACTOR nunca vira motivo
    assert all(
        r["code"] != "venda"
        for r in economy.price_reasons(st2, mode="sell", item_id="pocao_cura", merchant=m)
    )


def test_price_reasons_table_phrases():
    """§3.3: uma frase fixa por código."""
    st, m = _merchant_state("quinquilharias_brekmar", "cerco1")
    texts = {r["code"]: r for r in economy.price_reasons(st, mode="buy", merchant=m)}
    assert texts["estado_local"]["text"] == "Brekmar está sitiada"
    assert texts["estado_local"]["direction"] == "encarece"
    assert texts["mercador"] == {
        "code": "mercador",
        "direction": "barateia",
        "text": "este mercador costuma cobrar pouco",
    }
    st, m = _merchant_state("mercado_anel_dourado", "plain")
    assert {
        "code": "mercador",
        "direction": "encarece",
        "text": "este mercador cobra caro por natureza",
    } in economy.price_reasons(st, mode="buy", merchant=m)
    st, m = _merchant_state("mercado_anel_dourado", "festa")
    fest = [r for r in economy.price_reasons(st, mode="buy", merchant=m) if r["code"] == "festa"]
    assert fest and fest[0]["text"] == "é tempo de Dia da Fundação"
    st, m = _merchant_state("ferreiro_skallgard", "keeper_hostil")
    rel = [r for r in economy.price_reasons(st, mode="buy", merchant=m) if r["code"] == "relacao"]
    assert rel and rel[0]["text"].endswith("despreza você") and rel[0]["direction"] == "encarece"
    from services import reputation as rep

    key, row = rep.find_keeper(st, "ferreiro_skallgard")
    st["npcs"][key] = {**row, "relationship_basis": {"fame": 1}}
    rel = [r for r in economy.price_reasons(st, mode="buy", merchant=m) if r["code"] == "relacao"]
    assert rel[0]["text"].endswith("despreza você e ouviu falar bem de você por aqui")
    found: dict[str, str] = {}
    for scenario in ("rota_bloqueada", "passo_fechado", "plain"):
        for mid in sorted(economy.MERCHANTS):
            st, m = _merchant_state(mid, scenario)
            for iid in _items(mid):
                for r in economy.price_reasons(st, mode="buy", item_id=iid, merchant=m):
                    found.setdefault(r["code"], r["text"])
    assert found["supply_rota"] == "mercadorias de fora não estão chegando"
    st, m = _merchant_state("ferreiro_skallgard", "passo_fechado")
    passo = economy.price_reasons(st, mode="buy", item_id="pocao_cura", merchant=m)
    assert {
        "code": "supply_passo",
        "direction": "encarece",
        "text": "a estação fechou o caminho por onde a mercadoria vinha",
    } in passo
    assert found["supply_local"] == "a mercadoria é feita aqui mesmo"
    st, m = _merchant_state("boticario_anel_ferro", "patente")
    pat = [r for r in economy.price_reasons(st, mode="buy", merchant=m) if r["code"] == "patente"]
    assert pat and pat[0]["text"].startswith("desconto pela sua patente em ")
    assert pat[0]["direction"] == "barateia"


def test_unknown_faction_generic_phrase(monkeypatch):
    """R12: fação desconhecida não é nomeada; conhecida, sim."""
    monkeypatch.setattr(economy, "_controller_disposition", lambda s, loc: "hostil")
    monkeypatch.setattr(economy.gr, "get_current_controller", lambda *a, **k: "legiao_ferro")
    st, m = _merchant_state("ferreiro_skallgard", "plain")
    rs = economy.price_reasons(st, mode="buy", item_id="pocao_cura", merchant=m)
    ctl = [r for r in rs if r["code"] == "controlador_hostil"][0]
    assert ctl["text"] == "quem manda aqui não vê você com bons olhos"
    st["faction_intel"] = {"legiao_ferro": {"known": True}}
    ctl = [
        r
        for r in economy.price_reasons(st, mode="buy", item_id="pocao_cura", merchant=m)
        if r["code"] == "controlador_hostil"
    ][0]
    assert ctl["text"].endswith(" manda aqui e é hostil a você")
    assert "legiao_ferro" not in ctl["text"]


def test_price_reasons_no_numbers_no_ids():
    """R16: nenhum dígito, %, x<dígito> nem id de merchant/facção/local."""
    import gamedata

    texts = _all_texts()
    assert texts
    ids = set(economy.MERCHANTS) | {f["id"] for f in gamedata.seed_factions()}
    ids |= {loc["id"] for loc in gamedata.WORLD_MAP["locations"]}
    for t in set(texts):
        assert not re.search(r"\d|%|x\d", t), t
        assert not any(i in t for i in ids), t


def test_route_reason_never_names_cause():
    """Oráculo §3.6 (4): a rota bloqueada só vira 'mercadorias de fora…'."""
    from tests.spec309_helpers import world_state_two_regions

    st = world_state_two_regions()
    st["factions"], st["faction_intel"], st["npcs"] = [], {}, {}
    _block_routes(st)
    st["world_projection"]["location_states"] = {"brekmar": {"state": "cerco", "severity": 3}}
    m = economy.MERCHANTS["ferreiro_skallgard"]
    texts = []
    for iid in (None, "pocao_cura", *_items("ferreiro_skallgard")):
        texts += [r["text"] for r in economy.price_reasons(st, mode="buy", item_id=iid, merchant=m)]
    assert "mercadorias de fora não estão chegando" in texts
    assert not any("Brekmar" in t or "sitiada" in t or "cerco" in t.lower() for t in texts)


def test_engine_off_no_location_reason(monkeypatch):
    """R13: sem motor `on`, o estado do local não vira motivo."""
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    st, m = _merchant_state("quinquilharias_brekmar", "cerco3")
    assert all(
        r["code"] not in ("estado_local", "festa")
        for r in economy.price_reasons(st, mode="buy", merchant=m)
    )


def test_price_reasons_never_raises():
    assert economy.price_reasons({}, mode="buy") == []
    assert economy.market_direction({}, {}) in ("", "alta", "baixa")


# --- R14: loot ----------------------------------------------------------------------------
def _shop_state(mid: str, scenario: str, text: str) -> dict:
    from langchain_core.messages import HumanMessage

    st, _m = _merchant_state(mid, scenario)
    st["messages"] = [HumanMessage(content=text)]
    st["loot_source"] = "SHOP"
    st["player"]["gold"] = 5000
    return st


def _capture_narrate(monkeypatch):
    import agents.loot as loot

    calls: list[str] = []

    def fake(context, fallback, canonical_summary=None):
        calls.append(context)
        return fallback

    monkeypatch.setattr(loot, "_narrate", fake)
    return loot, calls


def test_loot_narrate_context_has_reasons(monkeypatch):
    import gamedata

    loot, calls = _capture_narrate(monkeypatch)
    st = _shop_state("quinquilharias_brekmar", "cerco1", "compro algo")
    stock = economy.merchant_stock(st, "brekmar")[1]
    item = next(iter(stock))
    st["messages"][0].content = f"compro {gamedata.ARTIFACTS_DB[item]['name']}"
    out = loot.loot_node(st)
    assert calls, out
    ctx = calls[0]
    assert "MOTIVOS DO PREÇO (cite no máximo um, com palavras; nunca números):" in ctx
    assert "- encarece: Brekmar está sitiada" in ctx
    sistema = out["messages"][0].content.split("[SISTEMA]")[1]
    assert "sitiada" not in sistema


def test_loot_observe_unchanged(monkeypatch):
    loot, calls = _capture_narrate(monkeypatch)
    st = _shop_state("quinquilharias_brekmar", "cerco1", "examino o estoque e os precos")
    out = loot.loot_node(st)
    assert calls == []
    assert "Mercado de" in out["messages"][0].content
    assert "sitiada" not in out["messages"][0].content


def test_loot_no_reasons_no_line(monkeypatch):
    loot, _calls = _capture_narrate(monkeypatch)
    st = _shop_state("boticario_anel_ferro", "plain", "compro x")
    assert loot._price_reasons_context(st, "craft", None) == ""
    far = {**st, "world": {**st["world"], "current_location_id": "pantano_melancolia"}}
    assert loot._price_reasons_context(far, "buy", None) == ""  # sem mercador no local


# --- R15: NPC-mercador --------------------------------------------------------------------
def test_npc_keeper_block_present_only_for_keeper():
    import agents.npc as npc_mod
    from services import reputation as rep

    st, m = _merchant_state("ferreiro_skallgard", "cerco2")
    st = _keeper(st, "ferreiro_skallgard", 5)
    key, row = rep.find_keeper(st, "ferreiro_skallgard")
    block = npc_mod._commerce_block(st, row)
    assert block.startswith("<SEU_COMERCIO>") and block.rstrip().endswith("</SEU_COMERCIO>")
    assert "Seus preços hoje estão mais altos que o normal." in block
    assert "Skallgard está sitiada" in block and "Brekmar" not in block
    assert "Nunca diga números nem porcentagens." in block
    assert not re.search(r"\d|%", block)
    assert npc_mod._commerce_block(st, {"name": "Um Camponês"}) == ""
    far = {**st, "world": {**st["world"], "current_location_id": "brekmar"}}
    assert npc_mod._commerce_block(far, row) == ""


def test_npc_keeper_block_empty_without_reasons(monkeypatch):
    import agents.npc as npc_mod
    from services import reputation as rep

    st, m = _merchant_state("ferreiro_skallgard", "plain")
    st = _keeper(st, "ferreiro_skallgard", 5)
    key, row = rep.find_keeper(st, "ferreiro_skallgard")
    monkeypatch.setattr(economy, "price_reasons", lambda *a, **k: [])
    assert npc_mod._commerce_block(st, row) == ""
    monkeypatch.undo()
    st, m = _merchant_state("quinquilharias_brekmar", "plain")
    st = _keeper(st, "quinquilharias_brekmar", 5)
    key, row = rep.find_keeper(st, "quinquilharias_brekmar")
    if row:
        block = npc_mod._commerce_block(st, row)
        assert block == "" or "mais baixos que o normal" in block
