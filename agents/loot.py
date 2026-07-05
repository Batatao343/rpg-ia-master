"""
agents/loot.py — Loot, Comércio e Crafting (Fase 4.4: economia determinística).

Padrão do combate: o LLM só IDENTIFICA a intenção (TradeIntent) e NARRA o
resultado; preços, estoques, receitas e raridade de drop resolvem em Python
(services/economy.py). O antigo TransactionResult (LLM decidia sucesso, preço
e itens) morreu aqui.
"""
import random
from typing import List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from gamedata import get_location
from llm_setup import ModelTier, get_llm
from services import economy
from state import GameState


class TradeIntent(BaseModel):
    """A IA traduz a fala livre em UMA transação canônica (Python resolve)."""
    mode: Literal["buy", "sell", "craft"] = Field(description="buy=comprar, sell=vender, craft=forjar/criar.")
    item_ref: str = Field(description="Nome do item/receita como o jogador disse. NÃO invente.")
    qty: int = Field(default=1, description="Quantidade (default 1).")


def _last_human(state: GameState) -> str:
    for m in reversed(state.get("messages") or []):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


def _parse_trade_intent(state: GameState, loot_source: str, text: str) -> TradeIntent:
    """FAST + guard de FallbackLLM (isinstance). Fallback: heurística por fonte."""
    default_mode = "craft" if loot_source == "CRAFT" else "buy"
    fallback = TradeIntent(mode=default_mode, item_ref=text[:60] or "item", qty=1)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
        sys = SystemMessage(content=(
            "Você identifica transações de RPG. Classifique a fala do jogador em "
            "buy (comprar do mercador), sell (vender item próprio) ou craft "
            "(forjar/criar/melhorar). item_ref = o nome do item/receita citado. "
            f"Contexto da cena: {loot_source}."))
        res = llm.with_structured_output(TradeIntent).invoke(
            [sys, HumanMessage(content=text or "negociar")])
        if isinstance(res, TradeIntent) and res.item_ref:
            return res
    except Exception as e:
        print(f"⚠️ [TRADE PARSE] {e}")
    return fallback


def _narrate(context: str, fallback_text: str) -> str:
    """1 chamada SMART para prosa curta; qualquer falha cai no texto mecânico."""
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.SMART)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        # Gemini exige >=1 mensagem não-system (achado do smoke real 2026-07-05)
        res = llm.invoke([
            SystemMessage(content=(
                "Narre em 1-2 frases, tom dark fantasy (Valoria), o resultado MECÂNICO "
                "do jogador. NÃO altere números nem invente itens extras.")),
            HumanMessage(content=context),
        ])
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):  # Gemini pode devolver parts (smoke 2026-07-05)
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in text)
        text = str(text).strip()
        if text:
            return text
    except Exception as e:
        print(f"⚠️ [LOOT NARRATE] {e}")
    return fallback_text


def loot_node(state: GameState):
    player = dict(state["player"])
    player["inventory"] = list(player.get("inventory", []))
    loot_source = state.get("loot_source", "TREASURE")
    text = _last_human(state)
    world = dict(state.get("world") or {})

    # restock determinístico pelo relógio (barato, idempotente)
    world = economy.restock(world)
    work_state = {**state, "player": player, "world": world}

    # =========================================================
    # CRAFT / SHOP — Python decide, LLM narra
    # =========================================================
    if loot_source in ("CRAFT", "SHOP"):
        intent = _parse_trade_intent(state, loot_source, text)
        if intent.mode == "craft":
            outcome = economy.execute_craft(work_state, intent.item_ref)
        else:
            outcome = economy.execute_trade(work_state, intent.mode,
                                            intent.item_ref, intent.qty)

        if not outcome.get("ok"):
            msg = _narrate(f"TRANSAÇÃO RECUSADA: {outcome.get('reason')}",
                           f"🚫 {outcome.get('reason')}")
            return {"messages": [AIMessage(content=f"{msg}\n\n[SISTEMA] {outcome.get('reason')}")],
                    "world": world, "loot_source": None, "archive_due": True}

        delta = int(outcome.get("gold_delta", 0))
        sistema = (f"[SISTEMA] {'+' if outcome['mode'] == 'sell' else ''}"
                   f"{outcome['qty']}x {outcome['item_name']}"
                   f" | Ouro {'+' if delta >= 0 else ''}{delta}"
                   f" (total {outcome['player'].get('gold', 0)})")
        resumo = (f"{outcome['mode'].upper()}: {outcome['qty']}x {outcome['item_name']}, "
                  f"ouro {delta:+d}, ouro final {outcome['player'].get('gold', 0)}")
        msg = _narrate(resumo, "O negócio se fecha sem cerimônia.")
        result = {
            "player": outcome["player"],
            "world": outcome.get("world", world),
            "messages": [AIMessage(content=f"{msg}\n\n{sistema}")],
            "loot_source": None,
            "archive_due": True,
        }
        # Fase 6.2: posse de item único muda de mãos → evento do motor na fila
        if outcome.get("pending_events"):
            result["pending_world_events"] = (state.get("pending_world_events", []) or []) \
                + outcome["pending_events"]
        return result

    # =========================================================
    # TREASURE — raridade/item saem da TABELA da região (Python)
    # =========================================================
    loc = get_location(world.get("current_location_id", "")) or {}
    region_id = loc.get("region_id", "default")
    danger = int(world.get("danger_level", 1) or 1)
    # Fase 6.4: pista de rastro descoberta na estrada melhora ESTE baú (one-shot)
    boost = bool(world.pop("treasure_hint", False))
    roll = economy.roll_loot(region_id, danger, random.Random(),
                             projection=state.get("world_projection"),
                             bestiary_knowledge=state.get("bestiary_knowledge"),
                             turn=int(world.get("turn_count", 0) or 0),
                             boost=boost)

    player["gold"] = int(player.get("gold", 0)) + int(roll["gold"])
    achado = f"+{roll['gold']} de ouro"
    unique_events = []
    if roll["item_id"]:
        from inventory import add_item, is_unique, item_display, make_entry
        player["inventory"] = add_item(player["inventory"], roll["item_id"], 1)
        achado = f"{item_display(make_entry(roll['item_id']))} ({roll['rarity']}) e {achado}"
        if is_unique(roll["item_id"]):  # Fase 6.2: achou um único — fato do mundo
            unique_events.append(economy.claim_event(roll["item_id"], "player"))

    sistema = f"[SISTEMA] {achado}"
    msg = _narrate(
        f"O jogador vasculha {loc.get('name', 'o local')} (perigo {danger}) e encontra: {achado}.",
        "Você vasculha os escombros e recolhe o que a poeira escondia.")
    result = {
        "player": player,
        "world": world,
        "messages": [AIMessage(content=f"{msg}\n\n{sistema}")],
        "loot_source": None,
        "archive_due": True,
    }
    if unique_events:
        result["pending_world_events"] = (state.get("pending_world_events", []) or []) + unique_events
    return result
