"""
agents/loot.py — Loot, Comércio e Crafting (Fase 4.4: economia determinística).

Padrão do combate: o LLM só IDENTIFICA a intenção (TradeIntent) e NARRA o
resultado; preços, estoques, receitas e raridade de drop resolvem em Python
(services/economy.py). O antigo TransactionResult (LLM decidia sucesso, preço
e itens) morreu aqui.
"""

import random
import re
import unicodedata
from typing import List, Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from gamedata import get_location
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services import conflict_summary as conflict_summary_service
from services import economy, latency_flags, prose_guard
from services.turn_outcome import record_gain
from state import GameState


class TradeIntent(BaseModel):
    """A IA traduz a fala livre em UMA transação canônica (Python resolve)."""

    mode: Literal["buy", "sell", "craft", "observe"] = Field(
        description="buy=comprar, sell=vender, craft=forjar/criar, observe=consultar sem transacionar."
    )
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
    checked = conflict_summary_service.narrative_or_fallback(canonical_summary, proposed)
    if checked != proposed:
        return checked
    if canonical_summary.get("loot_obtido"):
        return conflict_summary_service.canonical_summary_text(canonical_summary)
    return checked


_QTY_HINT_RE = re.compile(
    r"\d|\b(?:dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quatorze|quinze|"
    r"dezesseis|dezessete|dezoito|dezenove|vinte|trinta|quarenta|cinquenta|sessenta|setenta|oitenta|noventa|"
    r"cem|cento|duzentos|mil|par|pares|punhado|dezena|dezenas|centena|centenas|duzia|duzias|meia|"
    r"varios|varias|alguns|algumas|todos|todas|muitos|muitas|bastante|bastantes)\b"
)


def _resolve_item_ref(state: GameState, mode: str | None, folded: str) -> str | None:
    """SPEC-317 R3 (puro): id canonico quando EXATAMENTE um item do catalogo (estoque do
    mercador local p/ ``buy``; receitas p/ ``craft``) aparece por nome normalizado no texto.
    None = ambiguo, ausente, ou quantidade explicita -> segue o CLASSIFY como antes."""
    if mode not in ("buy", "craft") or not folded or _QTY_HINT_RE.search(folded):
        return None
    try:
        names: dict[str, set[str]] = {}  # id -> nomes normalizados
        if mode == "buy":
            import copy

            # deepcopy: merchant_stock/_ensure_stock gravam no world que recebem
            world = copy.deepcopy(state.get("world") or {})
            _mid, stock = economy.merchant_stock(
                {**state, "world": world}, world.get("current_location_id", "")
            )
            for iid in (stock or {}).keys():
                name = (economy.ARTIFACTS_DB.get(iid) or {}).get("name", iid)
                names[iid] = {economy._fold_key(iid), economy._fold_key(name)}
        else:
            for rid, recipe in economy.RECIPES.items():
                result = recipe.get("result_id", "")
                name = (economy.ARTIFACTS_DB.get(result) or {}).get("name", "")
                names[rid] = {economy._fold_key(n) for n in (rid, result, name) if n}
        hits = [
            iid
            for iid, ns in names.items()
            if any(n and re.search(rf"\b{re.escape(n)}\b", folded) for n in ns)
        ]
    except Exception as e:  # silent-ok: o atalho nunca derruba o turno; cai no CLASSIFY
        _log_event("loot", "resolve_item_ref_failed", level="warning", error=type(e).__name__)
        return None
    return hits[0] if len(hits) == 1 else None


def _parse_trade_intent(state: GameState, loot_source: str, text: str) -> TradeIntent:
    """FAST + guard de FallbackLLM (isinstance). Fallback: heurística por fonte."""
    folded = "".join(
        ch
        for ch in unicodedata.normalize("NFD", str(text or "").lower())
        if not unicodedata.combining(ch)
    )
    # Uma intenção transacional explícita vence palavras como "preço"/"estoque".
    explicit_mode = next(
        (
            mode
            for mode, pattern in (
                ("sell", r"\b(?:vendo|vender|venda)\b"),
                ("craft", r"\b(?:forjo|forjar|fabrico|fabricar|crio|criar|melhoro|melhorar)\b"),
                ("buy", r"\b(?:compro|comprar|compra|adquiro|adquirir)\b"),
            )
            if re.search(pattern, folded)
        ),
        None,
    )
    if (
        explicit_mode is None
        and loot_source == "SHOP"
        and re.search(
            r"\b(?:examino|confiro|consulto|observo|reviso|anoto|comparo|"
            r"estoque|precos?|margem|ofertas?|escassez|catalogo|cotacao)\b",
            folded,
        )
    ):
        return TradeIntent(mode="observe", item_ref="mercado", qty=1)

    default_mode = explicit_mode or ("craft" if loot_source == "CRAFT" else "buy")
    fallback = TradeIntent(mode=default_mode, item_ref=text[:60] or "item", qty=1)
    # SPEC-317 R3: regex decidiu o modo e o item resolve sozinho no catalogo -> sem CLASSIFY.
    resolved = _resolve_item_ref(state, explicit_mode, folded)
    if resolved:
        _log_event("loot", "trade_intent_skipped_classify", mode=explicit_mode)
        return TradeIntent(mode=explicit_mode, item_ref=resolved, qty=1)
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        sys = SystemMessage(
            content=(
                "Você identifica transações de RPG. Classifique a fala do jogador em "
                "buy (comprar do mercador), sell (vender item próprio) ou craft "
                "(forjar/criar/melhorar). item_ref = o nome do item/receita citado. "
                f"Contexto da cena: {loot_source}."
            )
        )
        res = llm.with_structured_output(TradeIntent).invoke(
            [sys, HumanMessage(content=text or "negociar")]
        )
        if isinstance(res, TradeIntent) and res.item_ref:
            return res.model_copy(update={"mode": explicit_mode}) if explicit_mode else res
    except Exception as e:
        _log_event("loot", "trade_parse_failed", level="warning", error=type(e).__name__)
    return fallback


def _narrate(context: str, fallback_text: str, canonical_summary: dict | None = None) -> str:
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
            else "Narre em 1-2 frases, tom dark fantasy (Valoria), o resultado MECÂNICO "
            "do jogador. NÃO altere números nem invente itens extras."
        )
        res = llm.invoke(
            [
                SystemMessage(content=instruction),
                HumanMessage(content=context),
            ]
        )
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):  # Gemini pode devolver parts (smoke 2026-07-05)
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        text = prose_guard.sanitize_meta_preamble(str(text))
        if text:
            if canonical_summary:
                return _validated_narrative(canonical_summary, text)
            return text
    except Exception as e:
        _log_event("loot", "narrate_failed", level="warning", error=type(e).__name__)
    fallback = prose_guard.sanitize_meta_preamble(fallback_text)
    return _validated_narrative(canonical_summary, fallback) if canonical_summary else fallback


def _price_reasons_context(state: dict, mode: str, item_id: str | None) -> str:
    """SPEC-311 R14: linha de motivos do preço p/ o narrador (palavras, nunca números).
    '' sem mercador, fora de compra/venda ou sem motivo; nunca levanta."""
    if mode not in ("buy", "sell"):
        return ""
    try:
        loc = (state.get("world") or {}).get("current_location_id", "")
        here = economy.merchants_at(loc)
        if not here:
            return ""
        reasons = economy.price_reasons(
            state, mode=mode, item_id=item_id or None, merchant=here[0][1]
        )
        if not reasons:
            return ""
        verbs = (
            {"encarece": "paga mais", "barateia": "paga menos"}
            if mode == "sell"
            else {"encarece": "encarece", "barateia": "barateia"}
        )
        rows = "\n".join(f"- {verbs[r['direction']]}: {r['text']}" for r in reasons)
        return "MOTIVOS DO PREÇO (cite no máximo um, com palavras; nunca números):\n" + rows
    except Exception as e:
        _log_event("loot", "price_reasons_failed", level="warning", error=type(e).__name__)
        return ""


def _player_facing_message(prose: str, system: str) -> str:
    """Monta a mensagem sem tocar no ledger mecânico de sistema."""
    visible = prose_guard.normalize_protagonist_voice(str(prose or "").strip())
    return f"{visible}\n\n{system}"


def _rumor_cache_find(state, player: dict, world: dict, loc: dict, text: str) -> dict | None:
    """SPEC-315 P2-4: busca roteada para LOOT no alvo de um boato VERDADEIRO materializa o
    achado do boato (roll_loot capado) no lugar do sorteio generico. Nunca levanta."""
    try:
        from services import rumor_adoption as ra

        if ra.mode() != "on":
            return None
        day = int((world.get("world_clock") or {}).get("day", 1) or 1)
        view = {**state, "player": player, "world": world}
        inst = ra.due_materialization(
            view, "search", str(world.get("current_location_id") or ""), day, text
        )
        if inst is None or (inst.get("claim") or {}).get("kind") not in ra.LOOT_KINDS:
            return None
        upd, marked = ra.materialize(view, inst, day)
        mat = marked["materialization"]
        sim = ra.commit(state.get("world_sim") or {}, str(inst["rumor_id"]), day, mat)
        parts = []
        if mat.get("item_id"):
            from inventory import item_display, make_entry

            parts.append(item_display(make_entry(mat["item_id"])))
        if mat.get("gold"):
            parts.append(f"+{mat['gold']} de ouro")
        achado = " e ".join(parts) or "apenas vestígios de alguém que passou ali"
        msg = _narrate(
            f"O jogador procura em {loc.get('name', 'o local')} e encontra EXATAMENTE: {achado}.",
            "Você revira o lugar com paciência e algo aparece entre a poeira.",
            None,
        )
        gold_delta = int(upd["player"].get("gold", 0) or 0) - int(player.get("gold", 0) or 0)
        result = {
            "player": upd["player"],
            "world": upd["world"],
            "world_sim": sim,
            "messages": [AIMessage(content=_player_facing_message(msg, f"[SISTEMA] {achado}"))],
            "loot_source": None,
            "archive_due": True,
        }
        if upd.get("events"):  # claim de unico no mesmo caminho do loot generico
            result["pending_world_events"] = (state.get("pending_world_events", []) or []) + list(
                upd["events"]
            )
        bl = record_gain(state.get("turn_baseline"), "gold", gold_delta, "loot")
        if bl is not state.get("turn_baseline"):
            result["turn_baseline"] = bl
        return result
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("loot", "rumor_find_failed", exc)
        return None


_LEAN_TRADE_GOLD = 50  # SPEC-318 R5: so transacao >= 50 ouro (ou item unico) pede arquivista


def _turn_of(world: dict) -> int:
    return int((world or {}).get("turn_count", 0) or 0)


def _low(world: dict) -> dict:
    """SPEC-318 R5: marca `archive_low` so quando a politica `lean`/shadow vai le-la."""
    return {"archive_low": _turn_of(world)} if latency_flags.archive_low_wanted() else {}


def loot_node(state: GameState):
    player = dict(state["player"])
    player["inventory"] = list(player.get("inventory", []))
    loot_source = state.get("loot_source", "TREASURE")
    text = _last_human(state)
    world = dict(state.get("world") or {})
    conflict_summary = dict(state.get("conflict_summary") or {})

    # restock determinístico pelo relógio (barato, idempotente)
    world = economy.restock(world, projection=state.get("world_projection"))
    work_state = {**state, "player": player, "world": world}

    # =========================================================
    # CRAFT / SHOP — Python decide, LLM narra
    # =========================================================
    if loot_source in ("CRAFT", "SHOP"):
        intent = _parse_trade_intent(state, loot_source, text)
        market_before = economy.public_market_snapshot(work_state)
        if intent.mode == "observe":
            if not market_before:
                system = "[SISTEMA] Não há mercado disponível neste local."
            else:
                quotes = market_before.get("quotes") or []
                rows = [
                    f"- {q.get('item_name', q.get('item_id', 'item'))}: "
                    f"compra {int(q.get('buy_price', 0) or 0)} / "
                    f"venda {int(q.get('sell_price', 0) or 0)} moedas "
                    f"(estoque {int(q.get('stock', 0) or 0)})"
                    for q in quotes[:12]
                ]
                system = (
                    f"[SISTEMA] Mercado de {market_before.get('merchant_name', 'mercador')} "
                    "(consulta sem transação):\n" + ("\n".join(rows) or "- Sem ofertas.")
                )
            return {
                "messages": [AIMessage(content=system)],
                "world": world,
                "loot_source": None,
                "archive_due": False,
            }
        gold_before = int(player.get("gold", 0) or 0)
        inventory_before = list(player.get("inventory") or [])
        if intent.mode == "craft":
            outcome = economy.execute_craft(work_state, intent.item_ref)
        else:
            outcome = economy.execute_trade(work_state, intent.mode, intent.item_ref, intent.qty)

        economy.log_trade(intent.mode, outcome)  # SPEC-252 R3
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
            "reason_code": ("ok" if outcome.get("ok") else "rejected"),
            "location_id": str(world.get("current_location_id") or ""),
            "merchant_id": (market_before.get("merchant_id") if market_before else None),
            "gold_before": gold_before,
            "gold_after": int((outcome.get("player") or player).get("gold", gold_before) or 0),
            "gold_delta": int(outcome.get("gold_delta", 0) or 0),
            "unequipped": list(outcome.get("unequipped") or []),
            "inventory_before": inventory_before,
            "inventory_after": list((outcome.get("player") or player).get("inventory") or []),
            "stock_before": market_before.get("quotes", []) if market_before else [],
        }

        if not outcome.get("ok"):
            reasons_ctx = _price_reasons_context(work_state, intent.mode, outcome.get("item_id"))
            recusa = f"TRANSAÇÃO RECUSADA: {outcome.get('reason')}"
            msg = _narrate(
                f"{recusa}\n{reasons_ctx}" if reasons_ctx else recusa,
                f"🚫 {outcome.get('reason')}",
            )
            return {
                "messages": [
                    AIMessage(
                        content=_player_facing_message(msg, f"[SISTEMA] {outcome.get('reason')}")
                    )
                ],
                "world": world,
                "loot_source": None,
                "archive_due": True,
                **_low(world),  # SPEC-318 R5: recusa nao e memoria
                "last_economy_action": public_action,
            }

        delta = int(outcome.get("gold_delta", 0))
        item_delta = -int(outcome["qty"]) if outcome["mode"] == "sell" else int(outcome["qty"])
        sistema = (
            f"[SISTEMA] {item_delta:+d}x {outcome['item_name']}"
            f" | Ouro {'+' if delta >= 0 else ''}{delta}"
            f" (total {outcome['player'].get('gold', 0)})"
        )
        resumo = (
            f"{outcome['mode'].upper()}: {outcome['qty']}x {outcome['item_name']}, "
            f"ouro {delta:+d}, ouro final {outcome['player'].get('gold', 0)}"
        )
        reasons_ctx = _price_reasons_context(work_state, intent.mode, outcome.get("item_id"))
        msg = _narrate(
            f"{resumo}\n{reasons_ctx}" if reasons_ctx else resumo,
            "O negócio se fecha sem cerimônia.",
        )
        result = {
            "player": outcome["player"],
            "world": outcome.get("world", world),
            "messages": [AIMessage(content=_player_facing_message(msg, sistema))],
            "loot_source": None,
            "archive_due": True,
            "last_economy_action": {
                **public_action,
                "stock_after": (
                    economy.public_market_snapshot(
                        {
                            **work_state,
                            "player": outcome["player"],
                            "world": outcome.get("world", world),
                        }
                    )
                    or {}
                ).get("quotes", []),
            },
        }
        if outcome.get("npcs") is not None:  # SPEC-298 R17: keeper registrado pela transação
            result["npcs"] = outcome["npcs"]
        # SPEC-226 R10: ganho (venda) / gasto (compra/craft) individual no baseline.
        _bl = record_gain(state.get("turn_baseline"), "gold", delta, "loot")
        if _bl is not state.get("turn_baseline"):
            result["turn_baseline"] = _bl
        # Fase 6.2: posse de item único muda de mãos → evento do motor na fila
        if outcome.get("pending_events"):
            result["pending_world_events"] = (
                state.get("pending_world_events", []) or []
            ) + outcome["pending_events"]
        if abs(delta) < _LEAN_TRADE_GOLD and not outcome.get("pending_events"):
            result.update(_low(world))  # SPEC-318 R5: compra barata, sem unico
        return result

    # =========================================================
    # TREASURE — raridade/item saem da TABELA da região (Python)
    # =========================================================
    loc = get_location(world.get("current_location_id", "")) or {}
    # SPEC-315 P2-4: achado de boato; se ha corpo a saquear (pos-combate), o corpo vem primeiro
    rumor_find = (
        None
        if conflict_summary.get("mortos")
        else _rumor_cache_find(state, player, world, loc, text)
    )
    if rumor_find is not None:
        return rumor_find
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
    roll = economy.roll_loot(
        region_id,
        danger,
        random.Random(),
        projection=state.get("world_projection"),
        bestiary_knowledge=state.get("bestiary_knowledge"),
        turn=int(world.get("turn_count", 0) or 0),
        boost=boost,
    )

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
        loot_entries.append(
            {
                "kind": "item",
                "item_id": str(roll["item_id"]),
                "qty": 1,
                "rarity": str(roll["rarity"]),
            }
        )
    if conflict_summary:
        conflict_summary["loot_obtido"] = loot_entries
    canonical_context = (
        conflict_summary_service.canonical_summary_text(conflict_summary)
        if conflict_summary
        else ""
    )
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
    elif not unique_events:
        result.update(_low(world))  # SPEC-318 R5: achado comum, sem unico
    _bl = record_gain(state.get("turn_baseline"), "gold", int(roll["gold"]), "loot")  # SPEC-226 R10
    if _bl is not state.get("turn_baseline"):
        result["turn_baseline"] = _bl
    if unique_events:
        result["pending_world_events"] = (
            state.get("pending_world_events", []) or []
        ) + unique_events
    return result
