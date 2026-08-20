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

import copy
import random
from typing import Any, Dict, List, Mapping, Optional, Tuple, TypedDict

from gamedata import ARTIFACTS_DB, get_location, load_json_data
from inventory import (add_item, find_in_inventory, get_qty, item_display,
                       make_entry, remove_item, resolve_item_name, _fold)
from services import graph_resolver as gr

RECIPES: Dict[str, dict] = load_json_data("recipes.json") or {}
MERCHANTS: Dict[str, dict] = load_json_data("merchants.json") or {}
LOOT_TABLES: Dict[str, dict] = load_json_data("loot_tables.json") or {}


class MarketQuote(TypedDict):
    item_id: str
    item_name: str
    stock: int
    buy_price: int
    sell_price: int


class PublicMarketSnapshot(TypedDict):
    location_id: str
    merchant_id: str
    merchant_name: str
    day: int
    turn: int
    quotes: List[MarketQuote]
    known_recipes: List[str]

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


# ---------------------------------------------------------------------------
# Fase 6.1 — rotas comerciais: alcançabilidade e escassez
# ---------------------------------------------------------------------------
SCARCE_MULT = 1.8


def _blocked_pairs(projection: Optional[dict]) -> set:
    return {frozenset((r.get("a"), r.get("b")))
            for r in (projection or {}).get("blocked_routes", []) or []}


def is_reachable(loc_a: str, loc_b: str, projection: Optional[dict]) -> bool:
    """BFS nas connections do mapa MENOS as rotas bloqueadas (par não-direcionado)."""
    if loc_a == loc_b:
        return True
    blocked = _blocked_pairs(projection)
    seen = {loc_a}
    frontier = [loc_a]
    while frontier:
        cur = frontier.pop()
        for nxt in (get_location(cur) or {}).get("connections", []) or []:
            if nxt in seen or frozenset((cur, nxt)) in blocked:
                continue
            if nxt == loc_b:
                return True
            seen.add(nxt)
            frontier.append(nxt)
    return False


def producing_locations(item_id: str) -> List[str]:
    """Locais cujo economy_tags intersecta o do item (regiões produtoras)."""
    from gamedata import WORLD_MAP
    item_tags = set((ARTIFACTS_DB.get(item_id) or {}).get("economy_tags") or [])
    if not item_tags:
        return []
    return [l["id"] for l in WORLD_MAP.get("locations", [])
            if item_tags & set(l.get("economy_tags") or [])]


def supply_factor(item_id: str, location_id: str,
                  projection: Optional[dict] = None) -> float:
    """Fase 6.1: 0.6 produzido AQUI · 1.0 produtor alcançável · 1.8 escasso
    (todas as rotas até produtores bloqueadas). Item sem tags → 1.0 sempre."""
    producers = producing_locations(item_id)
    if not producers:
        return 1.0
    loc_tags = set((get_location(location_id) or {}).get("economy_tags") or [])
    item_tags = set((ARTIFACTS_DB.get(item_id) or {}).get("economy_tags") or [])
    if loc_tags & item_tags:
        return ABUNDANT_MULT
    if any(is_reachable(location_id, p, projection) for p in producers):
        return 1.0
    return SCARCE_MULT


def price(item_id: str, *, mode: str, state: dict,
          merchant: Optional[dict] = None) -> int:
    """Preço final determinístico. mode: 'buy' (jogador compra) | 'sell' (vende)."""
    location_id = (state.get("world") or {}).get("current_location_id", "")
    p = float(base_price(item_id))
    # Fase 6.1: escassez por alcançabilidade (subsume o regional_modifier da 4.4:
    # sem rota bloqueada os valores são idênticos)
    p *= supply_factor(item_id, location_id, state.get("world_projection"))
    if merchant:
        p *= float(merchant.get("price_mult", 1.0) or 1.0)
    if mode == "buy" and _controller_disposition(state, location_id) == "hostil":
        p *= HOSTILE_BUY_MULT
    if mode == "sell":
        p *= SELL_FACTOR
    return _round5(p)


# ---------------------------------------------------------------------------
# Fase 6.2 — itens únicos: um por mundo
# ---------------------------------------------------------------------------
def is_unique_available(item_id: str, projection: Optional[dict]) -> bool:
    """True se o item único ainda NÃO foi reclamado (ou não é único).
    holder="world" = voltou ao pool (saqueado no downed — spec balanceamento R3):
    pode reaparecer em loot/loja/inimigo como se nunca tivesse sido reclamado."""
    from inventory import is_unique
    if not is_unique(item_id):
        return True
    entry = ((projection or {}).get("unique_items") or {}).get(item_id)
    return entry is None or entry.get("holder") == "world"


def unique_holder(item_id: str, projection: Optional[dict]) -> Optional[str]:
    entry = ((projection or {}).get("unique_items") or {}).get(item_id)
    return entry.get("holder") if entry else None


def claim_event(item_id: str, holder: str = "player") -> dict:
    """Evento de posse (source=engine — o LLM nunca propõe isto)."""
    etype = "unique_item_claimed" if holder == "player" else "unique_item_lost"
    return {"type": etype, "actor_id": "player", "target_id": item_id,
            "detail": f"posse de {item_id} -> {holder}",
            "payload": {"holder": holder}, "source": "engine"}


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
    # Fase 6.1: item escasso (produtores inalcançáveis) SOME da prateleira —
    # o mercador não vende o que não chega. Restock não repõe enquanto bloqueado
    # (o estoque base segue lá; a view esconde até route_cleared).
    proj = state.get("world_projection")
    stock = {iid: q for iid, q in stock.items()
             if supply_factor(iid, location_id, proj) < SCARCE_MULT}
    # Fase 6.2: único já reclamado some — EXCETO se o dono atual é ESTE mercador
    # (jogador vendeu pra ele; segue recomprável, rastreado no event_log).
    stock = {iid: q for iid, q in stock.items()
             if is_unique_available(iid, proj) or unique_holder(iid, proj) == mid}
    return mid, {iid: q for iid, q in stock.items() if q > 0}


def public_market_snapshot(
    state: Mapping[str, Any],
) -> Optional[PublicMarketSnapshot]:
    """Visão pública e read-only do mercado no local atual.

    `merchant_stock` inicializa estoque por compatibilidade com o motor. Para uma
    observação não mutar o jogo, trabalhamos sobre uma cópia profunda e usamos
    exatamente a mesma função/preço canônicos da transação real.
    """
    work = copy.deepcopy(dict(state))
    world = work.get("world") or {}
    location_id = str(world.get("current_location_id") or "")
    mid, stock = merchant_stock(work, location_id)
    if not mid:
        return None
    merchant = MERCHANTS.get(mid) or {}
    quotes: List[MarketQuote] = []
    for item_id, qty in sorted(stock.items()):
        quotes.append({
            "item_id": item_id,
            "item_name": item_display(make_entry(item_id)),
            "stock": int(qty or 0),
            "buy_price": price(item_id, mode="buy", state=work, merchant=merchant),
            "sell_price": price(item_id, mode="sell", state=work, merchant=merchant),
        })
    quoted_ids = {quote["item_id"] for quote in quotes}
    # Um mercador visível também pode cotar publicamente os itens que o jogador
    # carrega, ainda que não os tenha em estoque. ``stock=0`` impede compra, mas
    # permite decidir a venda sem ler tabelas privadas.
    inventory_ids = sorted({
        str(entry.get("id") or "")
        for entry in (work.get("player") or {}).get("inventory") or []
        if isinstance(entry, dict) and int(entry.get("qty", 1) or 0) > 0
    } - quoted_ids - {""})
    for item_id in inventory_ids:
        quotes.append({
            "item_id": item_id,
            "item_name": item_display(make_entry(item_id)),
            "stock": 0,
            "buy_price": price(item_id, mode="buy", state=work, merchant=merchant),
            "sell_price": price(item_id, mode="sell", state=work, merchant=merchant),
        })
    location = get_location(location_id) or {}
    craft_tags = set(location.get("craft_tags") or [])
    known_recipes = sorted(
        rid for rid, recipe in RECIPES.items()
        if not recipe.get("craft_tag") or recipe.get("craft_tag") in craft_tags
    )
    clock = world.get("world_clock") or {}
    return {
        "location_id": location_id,
        "merchant_id": mid,
        "merchant_name": str(merchant.get("name") or mid),
        "day": int(clock.get("day", 1) or 1),
        "turn": int(world.get("turn_count", 0) or 0),
        "quotes": quotes,
        "known_recipes": known_recipes,
    }


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
        out = {"ok": True, "mode": "buy", "item_id": iid,
               "item_name": item_display(make_entry(iid)), "qty": qty,
               "gold_delta": -total, "player": player, "world": world}
        # Fase 6.2: comprar um único registra a posse (inclusive recompra do mercador)
        from inventory import is_unique
        if is_unique(iid):
            out["pending_events"] = [claim_event(iid, "player")]
        return out

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
        out = {"ok": True, "mode": "sell", "item_id": iid,
               "item_name": item_display(make_entry(iid)), "qty": qty,
               "gold_delta": total, "player": player, "world": world}
        # Fase 6.2: vender um único → mercador SEGURA o item (recomprável,
        # nunca volta ao pool de drop) e a perda entra no event_log.
        from inventory import is_unique
        if is_unique(iid) and mid:
            stocks = world.setdefault("merchant_stocks", {}).setdefault(mid, {})
            stocks[iid] = stocks.get(iid, 0) + qty
            out["pending_events"] = [claim_event(iid, mid)]
        return out

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

    # Fase 6.2: receita de item ÚNICO já existente no mundo falha — não há segundo.
    if not is_unique_available(recipe.get("result_id", ""), state.get("world_projection")):
        return {"ok": False, "reason": "Esse artefato já existe no mundo — não há como forjar outro."}

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
def roll_loot(region_id: str, danger: int, rng: Optional[random.Random] = None,
              projection: Optional[dict] = None,
              bestiary_knowledge: Optional[dict] = None, turn: int = 0,
              boost: bool = False) -> dict:
    """Sorteia raridade (pesos por banda de perigo) e item do pool da região.
    Retorna {"item_id", "rarity", "gold"} — item_id None se pool vazio (só ouro).
    Fase 6.2: único já reclamado sai do pool ANTES do sorteio (nunca re-dropa).
    Fase 6.3: drops de criaturas quase-extintas na região somem temporariamente.
    Fase 6.4: `boost` (pista de rastro) força a banda alta — one-shot."""
    rng = rng or random.Random()
    table = LOOT_TABLES.get(region_id) or LOOT_TABLES.get("default") or {}
    band = "3-4" if boost else ("1-2" if int(danger or 1) <= 2 else "3-4")
    weights: Dict[str, int] = dict(table.get(band) or {"comum": 100})
    rarities = list(weights.keys())
    pick = rng.choices(rarities, weights=[max(0, int(weights[r])) for r in rarities], k=1)[0]
    pools = table.get("pools") or {}
    suppressed: set = set()
    if bestiary_knowledge is not None:
        from gamedata import BESTIARY
        from services.ecology import suppressed_loot
        suppressed = suppressed_loot(region_id, BESTIARY or {}, bestiary_knowledge, turn)
    pool = [i for i in (pools.get(pick) or [])
            if i in ARTIFACTS_DB and is_unique_available(i, projection)
            and i not in suppressed]
    item_id = rng.choice(pool) if pool else None
    gold = rng.randint(3, 12) * max(1, int(danger or 1))
    return {"item_id": item_id, "rarity": pick, "gold": gold}
