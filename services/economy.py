"""
services/economy.py — Economia determinística (Fase 4.4).

Padrão do combate aplicado ao comércio: o LLM só identifica a intenção
(TradeIntent) e narra o resultado; TODOS os números (preço, estoque, receita,
raridade de drop) resolvem aqui, em Python puro e testável offline.

Preço = base(raridade|value_gold) × mod_regional(economy_tags) × mult_mercador
        × mod_reputação(fação controladora do local — projection 2.5+) [× 0.5 venda]
LLM NUNCA decide preço; `gold_value` proposto pela IA para item novo é ignorado.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from gamedata import ARTIFACTS_DB, get_location, load_json_data
from inventory import (add_item, find_in_inventory, get_qty, item_display,
                       make_entry, remove_item, resolve_item_name, _fold)
from services import graph_resolver as gr

RECIPES: Dict[str, dict] = load_json_data("recipes.json") or {}
MERCHANTS: Dict[str, dict] = load_json_data("merchants.json") or {}
LOOT_TABLES: Dict[str, dict] = load_json_data("loot_tables.json") or {}

RARITY_BASE = {
    "common": 25, "comum": 25,
    "uncommon": 100, "incomum": 100,
    "rare": 400, "raro": 400,
    "epic": 1500, "epico": 1500, "épico": 1500,
    "legendary": 6000, "lendario": 6000, "lendário": 6000,
}
SELL_FACTOR = 0.5
HOSTILE_BUY_MULT = 1.5
ABUNDANT_MULT = 0.6
_RARITY_RANK = {"comum": 0, "common": 0, "incomum": 1, "uncommon": 1,
                "raro": 2, "rare": 2, "epico": 3, "epic": 3, "épico": 3,
                "lendario": 4, "lendário": 4, "legendary": 4}


def _round5(v: float) -> int:
    return max(1, int(round(v / 5.0) * 5))


def base_price(item_id: str) -> int:
    item = ARTIFACTS_DB.get(item_id) or {}
    vg = int(item.get("value_gold", item.get("gold_value", 0)) or 0)
    if vg > 0:
        return vg
    return RARITY_BASE.get(str(item.get("rarity", "comum")).lower(), 25)


def _controller_disposition(state: dict, location_id: str) -> str:
    """Disposition da fação que controla o local AGORA ('neutro' se desconhecida)."""
    controller = gr.get_current_controller(location_id, state.get("world_projection"))
    if not controller:
        return "neutro"
    for f in state.get("factions") or []:
        if f.get("id") == controller:
            return str(f.get("disposition", "neutro"))
    return "neutro"


def regional_modifier(item_id: str, location_id: str) -> float:
    """Item abundante na região (economy_tags do local ∩ do item) fica mais barato."""
    loc = get_location(location_id) or {}
    loc_tags = set(loc.get("economy_tags") or [])
    item_tags = set((ARTIFACTS_DB.get(item_id) or {}).get("economy_tags") or [])
    return ABUNDANT_MULT if loc_tags & item_tags else 1.0


def price(item_id: str, *, mode: str, state: dict,
          merchant: Optional[dict] = None) -> int:
    """Preço final determinístico. mode: 'buy' (jogador compra) | 'sell' (vende)."""
    location_id = (state.get("world") or {}).get("current_location_id", "")
    p = float(base_price(item_id))
    p *= regional_modifier(item_id, location_id)
    if merchant:
        p *= float(merchant.get("price_mult", 1.0) or 1.0)
    if mode == "buy" and _controller_disposition(state, location_id) == "hostil":
        p *= HOSTILE_BUY_MULT
    if mode == "sell":
        p *= SELL_FACTOR
    return _round5(p)


# ---------------------------------------------------------------------------
# Mercadores — estoque persistente no world state, restock por relógio
# ---------------------------------------------------------------------------
def merchants_at(location_id: str) -> List[Tuple[str, dict]]:
    return [(mid, m) for mid, m in MERCHANTS.items()
            if m.get("location_id") == location_id]


def _ensure_stock(world: dict, mid: str, merchant: dict) -> Dict[str, int]:
    stocks = world.setdefault("merchant_stocks", {})
    if mid not in stocks:
        stocks[mid] = dict(merchant.get("base_stock") or {})
        world.setdefault("merchant_restock_day", {})[mid] = int(
            (world.get("world_clock") or {}).get("day", 1) or 1)
    return stocks[mid]


def restock(world: dict) -> dict:
    """Reabastece mercadores vencidos pelo relógio (determinístico, idempotente)."""
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    stocks = world.get("merchant_stocks") or {}
    last = world.setdefault("merchant_restock_day", {})
    for mid, m in MERCHANTS.items():
        if mid in stocks and day - int(last.get(mid, day)) >= int(m.get("restock_days", 3)):
            stocks[mid] = dict(m.get("base_stock") or {})
            last[mid] = day
    return world


def merchant_stock(state: dict, location_id: str) -> Tuple[Optional[str], Dict[str, int]]:
    """(merchant_id, estoque EFETIVO). Local hostil esconde itens raros+ (R6)."""
    here = merchants_at(location_id)
    if not here:
        return None, {}
    mid, merchant = here[0]
    world = state.get("world") or {}
    stock = dict(_ensure_stock(world, mid, merchant))
    if _controller_disposition(state, location_id) == "hostil":
        stock = {iid: q for iid, q in stock.items()
                 if _RARITY_RANK.get(str((ARTIFACTS_DB.get(iid) or {}).get("rarity", "comum")).lower(), 0) < 2}
    return mid, {iid: q for iid, q in stock.items() if q > 0}


# ---------------------------------------------------------------------------
# Transações (buy / sell / craft) — o LLM só narra o TradeOutcome
# ---------------------------------------------------------------------------
def _resolve_ref_in(ref: str, candidates: List[str]) -> Optional[str]:
    rid = resolve_item_name(ref)
    if rid and rid in candidates:
        return rid
    folded = _fold(ref)
    for iid in candidates:
        name = _fold((ARTIFACTS_DB.get(iid) or {}).get("name", iid))
        if folded and (folded in name or folded in _fold(iid)):
            return iid
    return None


def execute_trade(state: dict, mode: str, item_ref: str, qty: int = 1) -> dict:
    """Compra/venda contra o mercador do local. Retorna TradeOutcome:
    {"ok", "reason", "item_id", "item_name", "qty", "gold_delta", "player", "world"}."""
    player = dict(state.get("player") or {})
    player["inventory"] = list(player.get("inventory") or [])
    world = dict(state.get("world") or {})
    location_id = world.get("current_location_id", "")
    qty = max(1, int(qty or 1))

    if mode == "buy":
        mid, stock = merchant_stock({**state, "world": world}, location_id)
        if not mid:
            return {"ok": False, "reason": "Não há mercador neste local."}
        _, merchant = mid, MERCHANTS.get(mid, {})
        iid = _resolve_ref_in(item_ref, list(stock.keys()))
        if not iid:
            return {"ok": False, "reason": f"O mercador não tem '{item_ref}' à venda."}
        if stock.get(iid, 0) < qty:
            return {"ok": False, "reason": f"Estoque insuficiente de {item_display(make_entry(iid))}."}
        unit = price(iid, mode="buy", state=state, merchant=merchant)
        total = unit * qty
        if int(player.get("gold", 0)) < total:
            return {"ok": False, "reason": f"Ouro insuficiente ({player.get('gold', 0)}/{total})."}
        player["gold"] = int(player.get("gold", 0)) - total
        player["inventory"] = add_item(player["inventory"], iid, qty)
        world["merchant_stocks"][mid][iid] = world["merchant_stocks"][mid].get(iid, 0) - qty
        return {"ok": True, "mode": "buy", "item_id": iid,
                "item_name": item_display(make_entry(iid)), "qty": qty,
                "gold_delta": -total, "player": player, "world": world}

    if mode == "sell":
        iid = find_in_inventory(player["inventory"], item_ref)
        if not iid:
            return {"ok": False, "reason": f"Você não tem '{item_ref}' para vender."}
        if get_qty(player["inventory"], iid) < qty:
            return {"ok": False, "reason": "Quantidade insuficiente."}
        mid, merchant = (merchants_at(location_id) or [(None, {})])[0]
        unit = price(iid, mode="sell", state=state, merchant=merchant or None)
        total = unit * qty
        player["inventory"], _ = remove_item(player["inventory"], iid, qty)
        player["gold"] = int(player.get("gold", 0)) + total  # sinal em PYTHON, sempre
        return {"ok": True, "mode": "sell", "item_id": iid,
                "item_name": item_display(make_entry(iid)), "qty": qty,
                "gold_delta": total, "player": player, "world": world}

    return {"ok": False, "reason": f"Modo de transação desconhecido: {mode!r}."}


def _fold_key(s: str) -> str:
    """fold + underscores viram espaço ('lamina_temperada' casa 'lâmina temperada')."""
    return _fold(str(s).replace("_", " "))


def find_recipe(ref: str) -> Optional[Tuple[str, dict]]:
    folded = _fold_key(ref)
    for rid, r in RECIPES.items():
        result = r.get("result_id", "")
        names = {_fold_key(rid), _fold_key(result),
                 _fold_key((ARTIFACTS_DB.get(result) or {}).get("name", ""))}
        if folded in names or any(folded and folded in n for n in names if n):
            return rid, r
    return None


def execute_craft(state: dict, item_ref: str) -> dict:
    """Craft com receita: valida local (craft_tag), ingredientes e ouro. Python decide."""
    player = dict(state.get("player") or {})
    player["inventory"] = list(player.get("inventory") or [])
    world = state.get("world") or {}
    loc = get_location(world.get("current_location_id", "")) or {}

    found = find_recipe(item_ref)
    if not found:
        return {"ok": False, "reason": f"Ninguém por aqui conhece uma receita de '{item_ref}'."}
    rid, recipe = found

    tag = recipe.get("craft_tag")
    if tag and tag not in (loc.get("craft_tags") or []):
        return {"ok": False, "reason": f"Este lugar não tem {tag} para esse trabalho."}

    classes_req = recipe.get("classes") or []
    if classes_req and player.get("class_name") not in classes_req:
        return {"ok": False, "reason": "Essa técnica não é do seu ofício."}

    for iid, need in (recipe.get("ingredients") or {}).items():
        if get_qty(player["inventory"], iid) < int(need):
            falta = item_display(make_entry(iid))
            return {"ok": False, "reason": f"Falta ingrediente: {falta} (precisa {need})."}

    cost = int(recipe.get("gold_cost", 0) or 0)
    if int(player.get("gold", 0)) < cost:
        return {"ok": False, "reason": f"Ouro insuficiente ({player.get('gold', 0)}/{cost})."}

    for iid, need in (recipe.get("ingredients") or {}).items():
        player["inventory"], _ = remove_item(player["inventory"], iid, int(need))
    player["gold"] = int(player.get("gold", 0)) - cost
    result_id = recipe.get("result_id")
    player["inventory"] = add_item(player["inventory"], result_id,
                                   int(recipe.get("result_qty", 1) or 1))
    return {"ok": True, "mode": "craft", "recipe_id": rid, "item_id": result_id,
            "item_name": item_display(make_entry(result_id)),
            "qty": int(recipe.get("result_qty", 1) or 1),
            "gold_delta": -cost, "player": player, "world": dict(world)}


# ---------------------------------------------------------------------------
# Drop tables — raridade rolada em Python (LLM só descreve)
# ---------------------------------------------------------------------------
def roll_loot(region_id: str, danger: int, rng: Optional[random.Random] = None) -> dict:
    """Sorteia raridade (pesos por banda de perigo) e item do pool da região.
    Retorna {"item_id", "rarity", "gold"} — item_id None se pool vazio (só ouro)."""
    rng = rng or random.Random()
    table = LOOT_TABLES.get(region_id) or LOOT_TABLES.get("default") or {}
    band = "1-2" if int(danger or 1) <= 2 else "3-4"
    weights: Dict[str, int] = dict(table.get(band) or {"comum": 100})
    rarities = list(weights.keys())
    pick = rng.choices(rarities, weights=[max(0, int(weights[r])) for r in rarities], k=1)[0]
    pools = table.get("pools") or {}
    pool = [i for i in (pools.get(pick) or []) if i in ARTIFACTS_DB]
    item_id = rng.choice(pool) if pool else None
    gold = rng.randint(3, 12) * max(1, int(danger or 1))
    return {"item_id": item_id, "rarity": pick, "gold": gold}
