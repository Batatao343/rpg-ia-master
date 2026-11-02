"""services/card_shop.py - Loja de Cartas neutras do mercador (SPEC-357).

Puro e deterministico, ZERO LLM. A prateleira nao e persistida: sai de
`random.Random(f"{game_id}:{mid}:{epoca}:cartas")` (epoca = dia // restock_days do mercador),
entao o mesmo estado sempre mostra a mesma prateleira e nenhum campo novo entra no save.
O preco vem de `data/cards/_loja.json` x fatores locais de `services.economy`.
Escrita so com `RPG_CARD_REWARDS=on` (D1: sem flag nova); a Carta entra pelo mesmo
caminho do espolio (`card_rewards.add_to_deck`).
"""

from __future__ import annotations

import json
import os
import random
from typing import Any

import gamedata
from services import card_rewards, card_telemetry, cards, economy

_RARITY_ORDER = {"comum": 0, "incomum": 1, "rara": 2}
_CONFIG: dict | None = None


def _config() -> dict:
    global _CONFIG
    if _CONFIG is None:
        path = os.path.join(gamedata.DATA_DIR, "cards", "_loja.json")
        try:
            with open(path, encoding="utf-8") as f:
                _CONFIG = json.load(f)
        except (OSError, ValueError) as exc:
            from observability.telemetry import log_fallback

            log_fallback("card_shop", "config_unreadable", exc)
            _CONFIG = {}
    return _CONFIG


def reload_config() -> None:
    global _CONFIG
    _CONFIG = None


def shelf_config(mid: str) -> dict | None:
    row = (_config().get("mercadores") or {}).get(mid)
    return row if isinstance(row, dict) else None


def _excluded(card_id: str, cfg: dict) -> bool:
    for pat in cfg.get("excluir") or []:
        if card_id == pat or (str(pat).endswith("_") and card_id.startswith(str(pat))):
            return True
    return False


def _merchant_here(state: dict) -> tuple[str, dict] | None:
    loc = (state.get("world") or {}).get("current_location_id", "")
    here = economy.merchants_at(str(loc))
    return here[0] if here else None


def _hostile(state: dict, mid: str, merchant: dict) -> bool:
    from services.reputation import npc_tier

    loc = (state.get("world") or {}).get("current_location_id", "")
    if economy._controller_disposition(state, str(loc)) == "hostil":
        return True
    keeper = economy._keeper_row(state, merchant)
    return bool(keeper) and npc_tier(keeper.get("relationship")) == "hostil"


def _closed(state: dict, merchant: dict) -> bool:
    from services.location_states import location_effects

    return bool(location_effects(state, str(merchant.get("location_id") or ""))["merchant_closed"])


def shelf_pool(state: dict, mid: str) -> list[str]:
    """R3/R5: pool elegivel (ordenado por id) do mercador `mid` para o jogador atual."""
    cfg = shelf_config(mid)
    merchant = economy.MERCHANTS.get(mid)
    if cfg is None or merchant is None:
        return []
    player = state.get("player") or {}
    regions = {str(r) for r in cfg.get("regioes") or []}
    gerais = bool(cfg.get("gerais"))
    hide_rare = _hostile(state, mid, merchant)
    out: list[str] = []
    for cid, c in sorted(cards.all_cards().items()):
        if not card_rewards.neutral_eligible(c, player):
            continue
        if _excluded(cid, cfg):
            continue
        region = c.get("regiao")
        if not ((region and str(region) in regions) or (gerais and not region)):
            continue
        if hide_rare and card_rewards.rarity_of(c) == "rara":
            continue
        out.append(cid)
    return out


def _epoch(state: dict, merchant: dict) -> int:
    day = int(((state.get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
    return day // max(1, int(merchant.get("restock_days", 3) or 3))


def shelf(state: dict) -> tuple[str | None, list[str]]:
    """R4: (merchant_id, ids da prateleira atual). Sem mercador/loja fechada/sem config -> vazio."""
    found = _merchant_here(state)
    if not found:
        return None, []
    mid, merchant = found
    if shelf_config(mid) is None or _closed(state, merchant):
        return mid, []
    pool = shelf_pool(state, mid)
    size = int(_config().get("prateleira", 3) or 3)
    rng = random.Random(f"{state.get('game_id', '')}:{mid}:{_epoch(state, merchant)}:cartas")
    picked = rng.sample(pool, min(size, len(pool)))

    def key(cid: str) -> tuple:
        c = cards.get_card(cid) or {}
        return (
            _RARITY_ORDER.get(card_rewards.rarity_of(c), 9),
            str(c.get("name", cid)).lower(),
            cid,
        )

    return mid, sorted(picked, key=key)


def card_price(state: dict, card_id: str, merchant: dict | None) -> int:
    """R6: (base da raridade + degrau por tier) x fatores locais de compra, arredondado a 5."""
    cfg = _config()
    card = cards.get_card(card_id) or {}
    rarity = card_rewards.rarity_of(card)
    base = float((cfg.get("preco_raridade") or {}).get(rarity, 0) or 0)
    tier = max(1, int(card.get("tier", 1) or 1))
    base += float(cfg.get("preco_por_tier", 0) or 0) * (tier - 1)
    return economy._round5(base * economy.local_buy_mult(state, merchant))


def _refusal(state: dict, mid: str, merchant: dict) -> str | None:
    out = economy._keeper_refusal(state, mid, merchant)
    return str(out["reason"]) if out else None


def _planned_destino(player: dict, card_id: str) -> str:
    return card_rewards.add_to_deck(dict(player), card_id)  # copia rasa: so reatribui chaves


def _planned_motivo(player: dict, card_id: str) -> dict:
    """SPEC-363 R32: quando o destino é o Acervo, diz o motivo (nunca "Baralho cheio" sem estar cheio)."""
    if _planned_destino(player, card_id) != "acervo":
        return {}
    why = card_rewards.acervo_reason(dict(player), card_id)
    return {"destino_motivo": why} if why else {}


def public_shop(state: dict) -> dict | None:
    """R8: bloco `player_stats.loja_cartas`. Puro (nao muta o state)."""
    if card_rewards.mode() != "on":
        return None
    allowed, _reason = cards.reorganize_status(state)
    if not allowed:
        return None
    mid, ids = shelf(state)
    if not mid or not ids:
        return None
    merchant = economy.MERCHANTS.get(mid) or {}
    player = state.get("player") or {}
    known = set(player.get("known_cards") or [])
    gold = int(player.get("gold", 0) or 0)
    motivo = _refusal(state, mid, merchant)
    day = int(((state.get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
    interval = max(1, int(merchant.get("restock_days", 3) or 3))
    offers = []
    for cid in ids:
        price = card_price(state, cid, merchant)
        conhecida = cid in known
        bloqueio: str | None = None
        if motivo:
            bloqueio = motivo
        elif conhecida:
            bloqueio = "Você já conhece essa Carta."
        elif gold < price:
            bloqueio = f"Faltam {price - gold} de ouro."
        offers.append(
            {
                **card_rewards.card_view(cid, player),
                "preco": price,
                "conhecida": conhecida,
                "destino": _planned_destino(player, cid),
                **_planned_motivo(player, cid),
                "bloqueio": bloqueio,
            }
        )
    return {
        "merchant_id": mid,
        "merchant_name": merchant.get("name", mid),
        "renova_em_dias": interval - (day % interval),
        "motivo": motivo,
        "ofertas": offers,
    }


@card_rewards._requires_on
def buy(state: dict, card_id: str) -> dict:
    """R7: compra 1 Carta da prateleira atual. Muta `state['player']` no lugar."""
    allowed, reason = cards.reorganize_status(state)
    if not allowed:
        return card_rewards._fail(reason or "Não é seguro negociar agora.", conflito=True)
    mid, ids = shelf(state)
    if not mid or not ids:
        return card_rewards._fail("Não há Cartas à venda aqui.")
    merchant = economy.MERCHANTS.get(mid) or {}
    if (motivo := _refusal(state, mid, merchant)) is not None:
        return card_rewards._fail(motivo)
    card_id = str(card_id or "")
    if card_id not in ids:
        return card_rewards._fail("Essa Carta não está à venda agora.")
    player = state["player"]
    if card_id in set(player.get("known_cards") or []):
        return card_rewards._fail("Você já conhece essa Carta.")
    card = cards.get_card(card_id) or {}
    if int(card.get("level_req", 1) or 1) > int(player.get("level", 1) or 1):
        return card_rewards._fail("Você ainda não tem nível para essa Carta.")
    price = card_price(state, card_id, merchant)
    gold = int(player.get("gold", 0) or 0)
    if gold < price:
        return card_rewards._fail(f"Faltam {price - gold} de ouro.")
    player["gold"] = economy.clamp_gold(player, gold - price)
    with card_telemetry.source_scope("loja"):
        card_telemetry.offered(ids, picked=card_id)
        card_telemetry.picked(card_id)
    why = card_rewards.acervo_reason(player, card_id)
    where = card_rewards.add_to_deck(player, card_id)
    name = card.get("name", card_id)
    return {
        "ok": True,
        "error": None,
        "card_id": card_id,
        "gold": price,
        "destino": where,
        **({"motivo": why} if where == "acervo" and why else {}),
        "log": f"{name} entra no seu Acervo" + (" e no Baralho." if where == "baralho" else "."),
    }


def match_offer(state: dict, folded_text: str) -> str | None:
    """R10: id da UNICA Carta da prateleira cujo nome (normalizado) aparece no texto."""
    if card_rewards.mode() != "on":
        return None
    _mid, ids = shelf(state)
    hits = [
        cid
        for cid in ids
        if (n := economy._fold_key((cards.get_card(cid) or {}).get("name", "")))
        and n in folded_text
    ]
    return hits[0] if len(hits) == 1 else None


def observe_lines(state: dict, limit: int = 3) -> list[str]:
    """R10(b): linhas 'Tecnica: X - compra N moedas' (so flag on, mercador com prateleira)."""
    if card_rewards.mode() != "on":
        return []
    mid, ids = shelf(state)
    if not mid:
        return []
    merchant = economy.MERCHANTS.get(mid) or {}
    known = set((state.get("player") or {}).get("known_cards") or [])
    lines = []
    for cid in ids:
        if cid in known:
            continue
        name = (cards.get_card(cid) or {}).get("name", cid)
        lines.append(f"Técnica: {name} — compra {card_price(state, cid, merchant)} moedas")
    return lines[:limit]


__all__: list[Any] = [
    "shelf_config",
    "shelf_pool",
    "shelf",
    "card_price",
    "public_shop",
    "buy",
    "match_offer",
    "observe_lines",
]
