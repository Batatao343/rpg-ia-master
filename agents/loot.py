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
from inventory import short_name
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services import card_shop, cards, economy, latency_flags, prose_guard
from services import conflict_summary as conflict_summary_service
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages, unwrap_player_input
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
    checked = conflict_summary_service.narrative_or_fallback(
        canonical_summary, proposed, player_facing=True
    )
    if checked != proposed:
        return checked
    if canonical_summary.get("loot_obtido"):
        return conflict_summary_service.player_summary_text(canonical_summary)
    return checked


CORPSE_ALREADY_LOOTED = "Você revira o corpo de novo; o que havia de valor já está com você."
_CORPSE_RE = re.compile(r"\b(?:corpos?|cadaver(?:es)?|restos|bolsos?)\b")


def _corpse_search(state: dict, combat: dict, world: dict, text: str) -> str:
    """SPEC-346 R20/R21: "claimed" = revistar o corpo de um encontro com espólio já reclamado
    (mesmo local); senão o rótulo de espécie do corpo citado; "" = busca no ambiente."""
    from services import encounter_manifest as em

    folded = em._fold(text)
    manifest = combat.get("encounter") if isinstance(combat, dict) else None
    labels = (
        [
            str(p.get("species_label") or "")
            for p in (manifest or {}).get("participants") or []
            if p.get("species_label")
        ]
        if em.is_valid_manifest(manifest)
        else []
    )
    mentions_label = any(em._fold(label) in folded for label in labels if label)
    if not (_CORPSE_RE.search(folded) or mentions_label):
        return ""
    result = combat.get("result") or {}
    if (
        combat.get("phase") == "ended"
        and result.get("loot_claimed")
        and str(result.get("location_id") or "") == str(world.get("current_location_id") or "")
        # o turno da própria vitória ainda reclama o espólio; só os turnos seguintes bloqueiam
        and int(result.get("loot_turn", 0) or 0) < int(world.get("turn_count", 0) or 0)
    ):
        return "claimed"
    return labels[0] if labels and _CORPSE_RE.search(folded) else ""


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


_CATALOG_RE = re.compile(
    r"\b(?:a venda|(?:pra|para) vender|(?<!me )vendem?|(?:esta|estao) vendendo|mercadorias?|"
    r"o que (?:voce|voces|ele|ela|a [a-z ]{1,30}?|o [a-z ]{1,30}?) tem)\b"
)
_QUESTION_RE = re.compile(r"^(?:o que|quanto|qual|quais|posso|tem|voces? tem|me vende)\b")


_PREFIX_STOP = frozenset("de da do das dos e com em a o as os um uma para pra no na".split())
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _prefix_match_len(item_name: str, folded: str) -> int:
    """SPEC-367 R1: maior prefixo (em tokens) do nome do item que aparece no texto com >= 2
    tokens significativos. 0 = nenhum."""
    tokens = _TOKEN_RE.findall(economy._fold_key(item_name.replace("…", " ")))
    for k in range(len(tokens), 1, -1):
        head = tokens[:k]
        if sum(1 for t in head if len(t) >= 3 and t not in _PREFIX_STOP) < 2:
            continue
        pat = r"\b" + r"[\s,;:.]+".join(re.escape(t) for t in head) + r"\b"
        if re.search(pat, folded):
            return k
    return 0


def _cites_inventory(state: GameState, folded: str) -> dict | None:
    """SPEC-364 R4: o texto cita (por nome inteiro) um item do inventario do heroi?
    SPEC-367 R1: senao, por prefixo significativo (ambiguo -> None)."""
    import inventory as inv

    entries = [e for e in (state.get("player") or {}).get("inventory") or [] if isinstance(e, dict)]
    for entry in entries:
        for name in {inv.item_display(entry), inv.short_display(entry)}:
            n = economy._fold_key(name)
            if len(n) >= 3 and re.search(rf"\b{re.escape(n)}\b", folded):
                return entry
    best, best_k, tie = None, 0, False
    for entry in entries:
        k = _prefix_match_len(inv.item_display(entry), folded)
        if k > best_k:
            best, best_k, tie = entry, k, False
        elif k and k == best_k and entry is not best:
            tie = True
    return None if tie else best


def _is_catalog_question(state: GameState, folded: str) -> bool:
    """SPEC-364 R4: pergunta de catalogo = marcador de catalogo e nenhum item citado
    (nem do inventario do heroi, nem da prateleira do mercador)."""
    if not _CATALOG_RE.search(folded) or _cites_inventory(state, folded):
        return False
    return _resolve_item_ref(state, "buy", folded) is None


def _is_shop_question(folded: str) -> bool:
    """SPEC-364 R6: '?' ou aberto por interrogativo."""
    return "?" in folded or bool(_QUESTION_RE.search(folded.strip()))


_BUY_ASK_RE = re.compile(r"\b(?:me vende|vende|vendem|comprar|compro|custa|custam|quanto custa)\b")
_SELL_ASK_RE = re.compile(r"\b(?:vender|vendo|vale|paga|pagam)\b")


def _shop_question_quote(work_state: dict, text: str) -> str | None:
    """SPEC-364 R6/D-364-3: pergunta no fluxo de itens NUNCA transaciona. Item resolvido ->
    cotacao dele; senao None (o chamador faz a consulta de R7)."""
    import inventory as inv

    folded = economy._fold_key(text)
    if not _is_shop_question(folded):
        return None
    entry = _cites_inventory(work_state, folded)
    snap = economy.public_market_snapshot(work_state)
    if not snap:
        return None
    # SPEC-364 P3-3: marcador de COMPRA ("me vende", "custa") cota o preço de compra do mercador
    # primeiro, mesmo que o herói também carregue o item; "vender/vale/paga" cota o de venda.
    if entry is not None and _BUY_ASK_RE.search(folded) and not _SELL_ASK_RE.search(folded):
        if _resolve_item_ref(work_state, "buy", folded):
            entry = None
        else:  # pediu para comprar algo que o mercador não tem: não confunde com cotação de venda
            return (
                f"[SISTEMA] {inv.short_display(entry)} não está à venda aqui. "
                "Para vender o seu, diga claramente que vende; nada mudou."
            )
    if entry is not None:
        shown = inv.short_display(entry)
        for q in snap.get("quotes") or []:
            if q.get("item_id") == entry.get("id") and q.get("item_name") == inv.item_display(
                entry
            ):
                return (
                    f"[SISTEMA] {shown}: o mercador paga {int(q.get('sell_price', 0) or 0)} moedas. "
                    "Diga claramente que vende para confirmar; nada mudou."
                )
        return None
    iid = _resolve_item_ref(work_state, "buy", folded)
    if iid:
        for q in snap.get("quotes") or []:
            if q.get("item_id") == iid and q.get("source") != "player":
                return (
                    f"[SISTEMA] {inv.short_name(q['item_name'])} custa "
                    f"{int(q.get('buy_price', 0) or 0)} moedas. "
                    "Diga claramente que compra para confirmar; nada mudou."
                )
    return None


def _observe_text(market: dict, work_state: dict, loot_source: str) -> str:
    """SPEC-364 R7/R8: 'À venda' (so estoque > 0) e 'Pelo que você carrega' (preco de venda)."""
    import inventory as inv

    quotes = [q for q in (market.get("quotes") or [])[:24] if str(q.get("item_name") or "").strip()]
    sale = [
        f"- {inv.short_name(q['item_name'])}: {int(q.get('buy_price', 0) or 0)} moedas "
        f"(estoque {int(q.get('stock', 0) or 0)})"
        for q in quotes
        if q.get("source") != "player" and int(q.get("stock", 0) or 0) > 0
    ][:12]
    if loot_source == "SHOP":  # SPEC-357 R10(b): técnicas à venda (flag on)
        sale += [f"- {ln}" for ln in card_shop.observe_lines(work_state)]
    carried = [
        f"- {inv.short_name(q['item_name'])}: paga {int(q.get('sell_price', 0) or 0)} moedas"
        for q in quotes
        if q.get("source") == "player"
    ][:12]
    nl = "\n"
    text = (
        f"[SISTEMA] Mercado de {market.get('merchant_name', 'mercador')} (consulta sem transação):{nl}"
        f"À venda:{nl}" + (nl.join(sale) or "- Sem ofertas.")
    )
    if carried:
        text += f"{nl}Pelo que você carrega:{nl}" + nl.join(carried)
    return text


def _parse_trade_intent(state: GameState, loot_source: str, text: str) -> TradeIntent:
    """FAST + guard de FallbackLLM (isinstance). Fallback: heurística por fonte."""
    folded = "".join(
        ch
        for ch in unicodedata.normalize("NFD", str(text or "").lower())
        if not unicodedata.combining(ch)
    )
    # SPEC-364 R4: pergunta de catálogo vira consulta, antes de qualquer regex de modo.
    if loot_source == "SHOP" and _is_catalog_question(state, folded):
        return TradeIntent(mode="observe", item_ref="mercado", qty=1)
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
                f"Contexto da cena: {loot_source}. " + PLAYER_INPUT_RULE
            )
        )
        res = llm.with_structured_output(TradeIntent).invoke(
            [sys, *guard_messages([HumanMessage(content=text or "negociar")])]
        )
        if isinstance(res, TradeIntent) and res.item_ref:
            res = res.model_copy(update={"item_ref": unwrap_player_input(res.item_ref)[:60]})
            return res.model_copy(update={"mode": explicit_mode}) if explicit_mode else res
    except Exception as e:
        _log_event("loot", "trade_parse_failed", level="warning", error=type(e).__name__)
    return fallback


def _merchant_context(merchant_name: object, location: object) -> str:
    """SPEC-364 R9: o narrador chama o mercador pelo nome (nunca inventa outro)."""
    name = str(merchant_name or "").strip()
    if not name:
        return ""
    where = f" ({location})" if location else ""
    return f"\nMercador: {name}{where}. Chame o mercador por esse nome; não invente outro."


def _deal_fallback(merchant_name: object) -> str:
    name = str(merchant_name or "").strip()
    return f"{name} fecha o negócio sem cerimônia." if name else "O negócio se fecha sem cerimônia."


def _gold_context(before: int, price: int, after: int) -> str:
    """SPEC-367 R15: saldo antes/preço/depois vindos do motor, para o narrador não inventar ouro."""
    rule = (
        " Se o ouro depois for maior que zero, nunca diga que foram as últimas moedas nem que a "
        "bolsa ficou vazia;"
        if after > 0
        else ""
    )
    tail = " não cite outro número de moedas." if rule else " Não cite outro número de moedas."
    return f"\nOuro antes: {before}. Preço: {abs(price)}. Ouro depois: {after}.{rule}{tail}"


def _narrate(
    context: str,
    fallback_text: str,
    canonical_summary: dict | None = None,
    gold_check: tuple[set[int], int] | None = None,
) -> str:
    """1 chamada SMART para prosa curta; qualquer falha cai no texto mecânico.
    SPEC-367 R16: `gold_check=(números permitidos, ouro depois)` aplica V-G à prosa."""
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
        from services.narrative_sink import narrate_text

        # SPEC-319 (27/10): loot nao streama. A prosa e curta (1-2 frases) e o texto final passa
        # por `_validated_narrative`/voz/ledger depois do stream, o que virava `replace` (tail)
        # no staging; a narracao sai inteira pelo canal antecipado da SPEC-316.
        res = narrate_text(
            llm,
            [
                SystemMessage(content=instruction),
                HumanMessage(content=context),
            ],
            stream=False,
        )
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):  # Gemini pode devolver parts (smoke 2026-07-05)
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        text = prose_guard.sanitize_meta_preamble(str(text))
        if text and gold_check is not None:
            allowed, after = gold_check
            if not prose_guard.gold_claims_ok(text, allowed=allowed, gold_after=after):
                _log_event("loot", "trade_prose_rejected", level="warning")
                return prose_guard.sanitize_meta_preamble(fallback_text)
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
    return f"{visible}\n\n{system}" if visible else system


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


_RARITY_PT = {
    "incomum": "item incomum",
    "uncommon": "item incomum",
    "raro": "item raro",
    "rare": "item raro",
    "epico": "item épico",
    "épico": "item épico",
    "epic": "item épico",
    "lendario": "item lendário",
    "lendário": "item lendário",
    "legendary": "item lendário",
}


def _rarity_phrase(rarity: object) -> str:
    """SPEC-353 R35: raridade em palavra, e só quando não é `comum` ("Corda, item incomum")."""
    word = _RARITY_PT.get(str(rarity or "").strip().casefold())
    return f", {word}," if word else ""


def _shop_complement_names(work_state: dict, state: GameState) -> list[str]:
    """SPEC-363 R28: nomes (dobrados, sem pontuação) que podem completar "da/do/de/na/no <nome>"."""

    def plain(t: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", economy._fold_key(t))).strip()

    raw: list[str] = []
    merchant = economy.MERCHANTS.get(card_shop.shelf(work_state)[0] or "") or {}
    raw.append(str(merchant.get("name") or ""))
    world = work_state.get("world") or {}
    raw.append(str(world.get("current_location") or ""))
    try:
        from services import npc_layers

        raw += [str(n) for n in npc_layers.npcs_for_context(work_state)]
    except Exception as exc:  # noqa: BLE001 - complemento é conveniência; sem ele só o nome da Carta compra
        from observability.telemetry import log_fallback

        log_fallback("loot", "shop_complement_failed", exc)
    names = sorted({plain(n) for n in raw if plain(n)}, key=len, reverse=True)
    return names


def _card_shop_turn(work_state: dict, state: GameState, player: dict, world: dict, text: str):
    """SPEC-357 R10(a): 'compro <nome exato de UMA Carta da prateleira>' resolve em Python,
    sem LLM de classificacao. Qualquer outro texto devolve None (fluxo de itens intacto)."""
    folded = economy._fold_key(text)
    if not re.search(r"\b(?:compro|comprar|compra|adquiro|adquirir)\b", folded):
        return None
    # Venda/forja na mesma frase: o fluxo de itens decide (nunca gastar ouro aqui).
    if re.search(r"\b(?:vendo|vender|venda|forjo|forjar|fabrico|fabricar|crio|criar)\b", folded):
        return None
    card_id = card_shop.match_offer(work_state, folded)
    if card_id is None:
        return None

    # Gasto irreversível: só intenção afirmativa inequívoca compra. Negação, pergunta ou consulta
    # de preço -> responde com o preço e pede confirmação, sem debitar.
    # Gramática fechada: a frase INTEIRA normalizada precisa ser
    # [saudação curta] + [eu] + verbo de compra + [artigo] + nome exato + [por favor/agora/então].
    # Qualquer sobra (ressalva, condição, adiamento, desistência, pergunta) -> sem débito.
    def _plain(t: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()

    name_plain = re.escape(
        _plain(economy._fold_key((cards.get_card(card_id) or {}).get("name", "")))
    )
    greet = r"(?:(?:oi|ola|ei|entao|bem|certo|ok|pois|bom dia|boa tarde|boa noite) )*"
    verb = r"(?:compro|adquiro|quero comprar|quero adquirir|vou comprar|vou adquirir)"
    tail = r"(?: (?:por favor|agora|entao))*"
    # SPEC-363 R28: "... da <mercador | local | NPC presente>" — gramática continua fechada.
    owners = _shop_complement_names(work_state, state)
    complement = (
        rf"(?: (?:da|do|de|na|no) (?:{'|'.join(re.escape(o) for o in owners)}))?" if owners else ""
    )
    affirmative = re.fullmatch(
        rf"{greet}(?:eu )?{verb} (?:(?:o|a|um|uma) )?{name_plain}{complement}{tail}",
        _plain(folded),
    )
    doubtful = "?" in folded
    if not affirmative or doubtful:
        merchant = economy.MERCHANTS.get(card_shop.shelf(work_state)[0] or "") or {}
        cname = (cards.get_card(card_id) or {}).get("name", card_id)
        price = card_shop.card_price(work_state, card_id, merchant)
        return {
            "messages": [
                AIMessage(
                    content=f"[SISTEMA] {cname} custa {price} moedas. "
                    f"Diga claramente que compra {cname} para confirmar; nada foi cobrado."
                )
            ],
            "world": world,
            "loot_source": None,
            "archive_due": False,
        }
    gold_before = int(player.get("gold", 0) or 0)
    res = card_shop.buy(work_state, card_id)
    if not res.get("ok"):
        msg = _narrate(f"TRANSAÇÃO RECUSADA: {res.get('error')}", f"🚫 {res.get('error')}")
        return {
            "messages": [
                AIMessage(content=_player_facing_message(msg, f"[SISTEMA] {res.get('error')}"))
            ],
            "world": world,
            "loot_source": None,
            "archive_due": True,
            **_low(world),
        }
    name = (cards.get_card(card_id) or {}).get("name", card_id)
    total = int(player.get("gold", 0) or 0)
    sistema = f"[SISTEMA] +1 Carta: {name} | Ouro −{res['gold']} (total {total})"
    shop_name = (economy.MERCHANTS.get(card_shop.shelf(work_state)[0] or "") or {}).get("name")
    msg = _narrate(
        f"BUY: Carta {name}, ouro −{res['gold']}, ouro final {total}"
        + _gold_context(gold_before, int(res["gold"]), total)
        + _merchant_context(shop_name, world.get("current_location")),
        _deal_fallback(shop_name),
        gold_check=({gold_before, abs(int(res["gold"])), total}, total),
    )
    result = {
        "player": player,
        "world": world,
        "messages": [AIMessage(content=_player_facing_message(msg, sistema))],
        "loot_source": None,
        "archive_due": True,
    }
    _bl = record_gain(state.get("turn_baseline"), "gold", total - gold_before, "loot")
    if _bl is not state.get("turn_baseline"):
        result["turn_baseline"] = _bl
    if res["gold"] < _LEAN_TRADE_GOLD:
        result.update(_low(world))
    return result


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
        if loot_source == "SHOP":
            card_turn = _card_shop_turn(work_state, state, player, world, text)
            if card_turn is not None:
                return card_turn
        if loot_source == "SHOP":  # SPEC-364 R6: pergunta nunca transaciona item
            quote_text = _shop_question_quote(work_state, text)
            if quote_text:
                return {
                    "messages": [AIMessage(content=quote_text)],
                    "world": world,
                    "loot_source": None,
                    "archive_due": False,
                }
            if _is_shop_question(economy._fold_key(text)):
                intent = TradeIntent(mode="observe", item_ref="mercado", qty=1)
            else:
                intent = _parse_trade_intent(state, loot_source, text)
        else:
            intent = _parse_trade_intent(state, loot_source, text)
        market_before = economy.public_market_snapshot(work_state)
        if intent.mode == "observe":
            if not market_before:
                system = "[SISTEMA] Não há mercado disponível neste local."
            else:
                system = _observe_text(market_before, work_state, loot_source)
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
            f"[SISTEMA] {item_delta:+d}x {short_name(outcome['item_name'])}"
            f" | Ouro {'+' if delta >= 0 else ''}{delta}"
            f" (total {outcome['player'].get('gold', 0)})"
        )
        resumo = (
            f"{outcome['mode'].upper()}: {outcome['qty']}x {outcome['item_name']}, "
            f"ouro {delta:+d}, ouro final {outcome['player'].get('gold', 0)}"
        )
        reasons_ctx = _price_reasons_context(work_state, intent.mode, outcome.get("item_id"))
        merchant_ctx = _merchant_context(
            (market_before or {}).get("merchant_name"), world.get("current_location")
        )
        gold_after = int(outcome["player"].get("gold", 0) or 0)
        msg = _narrate(
            (f"{resumo}\n{reasons_ctx}" if reasons_ctx else resumo)
            + _gold_context(gold_before, delta, gold_after)
            + merchant_ctx,
            _deal_fallback((market_before or {}).get("merchant_name")),
            gold_check=({gold_before, abs(delta), gold_after}, gold_after),
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
    # SPEC-346 R20: revistar o corpo de um encontro cujo espólio já foi reclamado não rerrola.
    corpse = _corpse_search(state, combat, world, text)
    if corpse == "claimed":
        _log_event("loot", "corpse_already_looted", level="info")
        return {
            "messages": [AIMessage(content=CORPSE_ALREADY_LOOTED)],
            "loot_source": None,
            "archive_due": False,
        }
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
        achado = f"{item_display(make_entry(roll['item_id']))}{_rarity_phrase(roll['rarity'])} e {achado}"
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
    if conflict_summary:
        # SPEC-346 R18: pós-vitória o desfecho já foi narrado pelo combate; o loot só anexa o
        # espólio exato (sem LLM e sem repetir o resumo canônico).
        msg = ""
    else:
        subject = (
            f"o corpo de {corpse}"
            if corpse and corpse not in ("claimed", "")
            else loc.get("name", "o local")
        )
        msg = _narrate(
            f"FATOS CANÔNICOS DO CONFLITO: {canonical_context}\n"
            f"Você vasculha {subject} "
            f"(nível mecânico {danger}) e encontra EXATAMENTE: {achado}.",
            "Você vasculha os escombros; o resultado exato está no registro do motor.",
            None,
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
        ended = dict(combat)
        if ended.get("result"):  # SPEC-346 R19: o espólio do encontro é reclamado uma vez só
            ended["result"] = {
                **ended["result"],
                "loot_claimed": True,
                "loot_turn": int(world.get("turn_count", 0) or 0),
                "location_id": str(world.get("current_location_id") or ""),
            }
            result["combat"] = ended
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
