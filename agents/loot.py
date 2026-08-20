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
from services import conflict_summary as conflict_summary_service
from services import economy, prose_guard
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


def _validated_narrative(canonical_summary: dict, proposed_text: str) -> str:
    """Aceita atmosfera livre, mas nunca uma alegação livre de espólio.

    Não há fact-check lexical capaz de provar que um substantivo inventado é um
    item. Portanto, quando já existe loot aplicado, a prosa livre inteira cai no
    resumo determinístico. O resultado exato também permanece no rodapé de
    sistema.
    """
    proposed = str(proposed_text or "").strip()
    checked = conflict_summary_service.narrative_or_fallback(
        canonical_summary, proposed)
    if checked != proposed:
        return checked
    if canonical_summary.get("loot_obtido"):
        return conflict_summary_service.canonical_summary_text(canonical_summary)
    return checked


def _parse_trade_intent(state: GameState, loot_source: str, text: str) -> TradeIntent:
    """FAST + guard de FallbackLLM (isinstance). Fallback: heurística por fonte."""
    default_mode = "craft" if loot_source == "CRAFT" else "buy"
    fallback = TradeIntent(mode=default_mode, item_ref=text[:60] or "item", qty=1)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
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


def _narrate(context: str, fallback_text: str,
             canonical_summary: Optional[dict] = None) -> str:
    """1 chamada SMART para prosa curta; qualquer falha cai no texto mecânico."""
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        # Gemini exige >=1 mensagem não-system (achado do smoke real 2026-07-05)
        instruction = (
            "Narre em 1-2 frases apenas a ATMOSFERA da busca, sem citar ouro, "
            "quantidade, item ou aquisição; o resultado exato será anexado pelo "
            "motor."
            if canonical_summary and canonical_summary.get("loot_obtido")
            else
            "Narre em 1-2 frases, tom dark fantasy (Valoria), o resultado MECÂNICO "
            "do jogador. NÃO altere números nem invente itens extras."
        )
        res = llm.invoke([
            SystemMessage(content=instruction),
            HumanMessage(content=context),
        ])
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):  # Gemini pode devolver parts (smoke 2026-07-05)
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in text)
        text = prose_guard.sanitize_meta_preamble(str(text))
        if text:
            if canonical_summary:
                return _validated_narrative(canonical_summary, text)
            return text
    except Exception as e:
        print(f"⚠️ [LOOT NARRATE] {e}")
    fallback = prose_guard.sanitize_meta_preamble(fallback_text)
    return (_validated_narrative(canonical_summary, fallback)
            if canonical_summary else fallback)


def _player_facing_message(prose: str, system: str) -> str:
    """Monta a mensagem sem tocar no ledger mecânico de sistema."""
    visible = prose_guard.normalize_protagonist_voice(str(prose or "").strip())
    return f"{visible}\n\n{system}"


def loot_node(state: GameState):
    player = dict(state["player"])
    player["inventory"] = list(player.get("inventory", []))
    loot_source = state.get("loot_source", "TREASURE")
    text = _last_human(state)
    world = dict(state.get("world") or {})
    conflict_summary = dict(state.get("conflict_summary") or {})

    # restock determinístico pelo relógio (barato, idempotente)
    world = economy.restock(world)
    work_state = {**state, "player": player, "world": world}

    # =========================================================
    # CRAFT / SHOP — Python decide, LLM narra
    # =========================================================
    if loot_source in ("CRAFT", "SHOP"):
        intent = _parse_trade_intent(state, loot_source, text)
        market_before = economy.public_market_snapshot(work_state)
        gold_before = int(player.get("gold", 0) or 0)
        inventory_before = list(player.get("inventory") or [])
        if intent.mode == "craft":
            outcome = economy.execute_craft(work_state, intent.item_ref)
        else:
            outcome = economy.execute_trade(work_state, intent.mode,
                                            intent.item_ref, intent.qty)

        public_action = {
            "action_id": (
                f"{int(world.get('turn_count', 0) or 0)}:"
                f"{intent.mode}:{intent.item_ref}:{int(intent.qty or 1)}"
            ),
            "turn": int(world.get("turn_count", 0) or 0),
            "mode": intent.mode,
            "item_ref": intent.item_ref,
            "item_id": outcome.get("item_id"),
            "qty": int(outcome.get("qty", intent.qty) or 1),
            "ok": bool(outcome.get("ok")),
            "reason": str(outcome.get("reason") or ""),
            "reason_code": (
                "ok" if outcome.get("ok") else "rejected"
            ),
            "location_id": str(world.get("current_location_id") or ""),
            "merchant_id": (
                market_before.get("merchant_id") if market_before else None
            ),
            "gold_before": gold_before,
            "gold_after": int(
                (outcome.get("player") or player).get("gold", gold_before) or 0
            ),
            "gold_delta": int(outcome.get("gold_delta", 0) or 0),
            "inventory_before": inventory_before,
            "inventory_after": list(
                (outcome.get("player") or player).get("inventory") or []
            ),
            "stock_before": market_before.get("quotes", []) if market_before else [],
        }

        if not outcome.get("ok"):
            msg = _narrate(f"TRANSAÇÃO RECUSADA: {outcome.get('reason')}",
                           f"🚫 {outcome.get('reason')}")
            return {"messages": [AIMessage(content=_player_facing_message(
                        msg, f"[SISTEMA] {outcome.get('reason')}"))],
                    "world": world, "loot_source": None, "archive_due": True,
                    "last_economy_action": public_action}

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
            "messages": [AIMessage(content=_player_facing_message(msg, sistema))],
            "loot_source": None,
            "archive_due": True,
            "last_economy_action": {
                **public_action,
                "stock_after": (
                    economy.public_market_snapshot({
                        **work_state,
                        "player": outcome["player"],
                        "world": outcome.get("world", world),
                    }) or {}
                ).get("quotes", []),
            },
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
    combat = state.get("combat") or {}
    loot_ctx = conflict_summary_service.loot_context(
        conflict_summary,
        region_id=region_id,
        encounter_level=combat.get("encounter_level"),
        danger_level=int(world.get("danger_level", 1) or 1),
    )
    danger = int(loot_ctx["danger"])
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
    # Prompt, validação e archivist precisam observar o estado JÁ aplicado.
    loot_entries = list(conflict_summary.get("loot_obtido") or [])
    if int(roll["gold"]):
        loot_entries.append({"kind": "gold", "amount": int(roll["gold"])})
    if roll["item_id"]:
        loot_entries.append({
            "kind": "item", "item_id": str(roll["item_id"]),
            "qty": 1, "rarity": str(roll["rarity"]),
        })
    if conflict_summary:
        conflict_summary["loot_obtido"] = loot_entries
    canonical_context = (
        conflict_summary_service.canonical_summary_text(conflict_summary)
        if conflict_summary else "")
    msg = _narrate(
        f"FATOS CANÔNICOS DO CONFLITO: {canonical_context}\n"
        f"O jogador vasculha {loc.get('name', 'o local')} "
        f"(nível mecânico {danger}) e encontra EXATAMENTE: {achado}.",
        "Você vasculha os escombros; o resultado exato está no registro do motor.",
        conflict_summary or None,
    )
    result = {
        "player": player,
        "world": world,
        "messages": [AIMessage(content=_player_facing_message(msg, sistema))],
        "loot_source": None,
        "archive_due": True,
    }
    if conflict_summary:
        result["conflict_summary"] = conflict_summary
    if unique_events:
        result["pending_world_events"] = (state.get("pending_world_events", []) or []) + unique_events
    return result
