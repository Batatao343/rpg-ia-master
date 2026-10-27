"""services/card_piles.py - Baralho de Conflito, Mao, Descarte e Folego (SPEC-328).

Puro e deterministico, ZERO LLM. O estado vive em `combat["pilhas"]`:

    {compra, mao, descarte, exaurida, guardadas, folego, folego_emprestado,
     seed, embaralhos, fardos}

Toda aleatoriedade vem de `random.Random(f"{seed}:{embaralhos}")`; `embaralhos` e
persistido, entao um save/load no meio do conflito continua a mesma sequencia
(replay deterministico) sem tocar o `random` global do combate.

Flag `RPG_CARD_DECK=off|shadow|on` (padrao `off`; valor invalido tambem vira `off`).
"""

from __future__ import annotations

import copy
import os
import random
from collections.abc import Callable
from typing import Any, Literal

from services import cards

Mode = Literal["off", "shadow", "on"]

MAO_BASE = 5
FOLEGO_BASE = 3
PACTO_ENTROPIA_POR_FOLEGO = 2
PACTO_MAX_FOLEGO = 2
FARDO_ID = "fardo_estilhaco"
FARDO_CARD: dict[str, Any] = {
    "id": FARDO_ID,
    "name": "Estilhaço de Cinza",
    "tipo": "fardo",
    "frequencia": "livre",
    "descricao": "Um caco do Abismo entre as suas cartas: pesa na mão e não serve a ninguém.",
    "injogavel": True,
}

_NO_COST_MANEUVERS = {"mover"}
_FREE_KINDS = {"pass", "move"}


def mode() -> Mode:
    raw = str(os.getenv("RPG_CARD_DECK", "off") or "off").strip().lower()
    return raw if raw in ("off", "shadow", "on") else "off"  # type: ignore[return-value]


# ==========================================================================
# Baralho
# ==========================================================================
def _starting_deck_ids(player: dict) -> list[str]:
    """Baralho inicial (R2/R3): 4 golpes + 4 guardas + 1 assinatura + cartas ativas,
    de reacao e utilitarias das preparadas. Passivas/Virtude ficam como talentos."""
    basics = cards.basicas_for_class(str(player.get("class_name", "")))
    deck: list[str] = []
    deck += (basics["golpe"][:1] or []) * 4
    deck += (basics["guarda"][:1] or []) * 4
    deck += basics["assinatura"][:1]
    for cid in player.get("prepared_cards") or []:
        card = cards.get_card(cid) or {}
        if card.get("tipo") in cards._DECK_TIPOS and not card.get("basica"):
            deck.append(cid)
    # Postura sem basicas autoradas (fixtures/saves exoticos): completa com o que ha.
    pad = (basics["golpe"] + basics["guarda"])[:1]
    while pad and len(deck) < cards.DECK_MIN:
        deck.append(pad[0])
    return deck[: cards.DECK_MAX]


def activate_deck(player: dict) -> None:
    """Modo `on` (P1-3): garante baralho + `prepared_cards` derivado, guardando o original
    em `prepared_cards_pre_deck` para o rollback se a flag voltar a `off`."""
    if migrate_deck(player) or "prepared_cards_pre_deck" in player:
        return
    player["prepared_cards_pre_deck"] = list(player.get("prepared_cards") or [])
    keep = [
        c
        for c in player["prepared_cards"]
        if (cards.get_card(c) or {}).get("tipo") not in cards._DECK_TIPOS
    ]
    player["prepared_cards"] = list(dict.fromkeys(list(player.get("deck") or []) + keep))


def deactivate_deck(player: dict) -> None:
    """Flag voltou a `off`: restaura a Preparação anterior (o `deck` fica guardado)."""
    pre = player.pop("prepared_cards_pre_deck", None)
    if pre is not None:
        player["prepared_cards"] = list(pre)


def migrate_deck(player: dict) -> bool:
    """Migracao idempotente (R3). Devolve True se montou o baralho. Com `deck` valido
    nao mexe; `prepared_cards` e re-derivado do baralho (R4) preservando passivas."""
    existing = player.get("deck")
    changed = False
    if not (isinstance(existing, list) and existing):
        player["deck"] = _starting_deck_ids(player)
        changed = True
    if changed:
        player.setdefault("prepared_cards_pre_deck", list(player.get("prepared_cards") or []))
        keep = [
            c
            for c in (player.get("prepared_cards") or [])
            if (cards.get_card(c) or {}).get("tipo") not in cards._DECK_TIPOS
        ]
        player["prepared_cards"] = list(dict.fromkeys(list(player["deck"]) + keep))
    return changed


# ==========================================================================
# Pilhas
# ==========================================================================
def _rng(piles: dict, rng: random.Random | None = None) -> random.Random:
    if rng is not None:
        return rng
    n = int(piles.get("embaralhos", 0) or 0)
    piles["embaralhos"] = n + 1
    return random.Random(f"{int(piles.get('seed', 0) or 0)}:{n}")


def _locked_for_scene(player: dict, card_id: str) -> bool:
    """Carta de descanso_* ja gasta fica fora do baralho ate o descanso (R11)."""
    card = cards.get_card(card_id) or {}
    freq = str(card.get("frequencia", "livre"))
    if freq not in ("descanso_curto", "descanso_longo"):
        return False
    counter = cards.FREQ_COUNTER[freq]
    return int(((player.get("card_usage") or {}).get(card_id) or {}).get(counter, 0) or 0) >= 1


def start_piles(player: dict, seed: int, rng: random.Random | None = None) -> dict:
    """Inicio do conflito (R5): embaralha com a semente e compra a mao inicial."""
    deck_ids = list(player.get("deck") or []) or _starting_deck_ids(player)  # sem mutar a ficha
    live: list[str] = []
    out: list[str] = []
    for cid in deck_ids:
        (out if _locked_for_scene(player, cid) else live).append(cid)
    piles: dict[str, Any] = {
        "compra": live,
        "mao": [],
        "descarte": [],
        "exaurida": out,
        "guardadas": [],
        "folego": FOLEGO_BASE,
        "folego_emprestado": 0,
        "seed": int(seed),
        "embaralhos": 0,
        "fardos": 0,
        "pacto_carga": False,
    }
    _rng(piles, rng).shuffle(piles["compra"])
    draw(piles, MAO_BASE, rng)
    return piles


def reshuffle(piles: dict, rng: random.Random | None = None) -> None:
    """Descarte volta ao monte + 1 Fardo (R9)."""
    pool = list(piles["descarte"]) + [FARDO_ID]
    _rng(piles, rng).shuffle(pool)
    piles["compra"] = list(piles["compra"]) + pool
    piles["descarte"] = []
    piles["fardos"] = int(piles.get("fardos", 0) or 0) + 1


def draw(piles: dict, n: int, rng: random.Random | None = None) -> list[str]:
    drawn: list[str] = []
    for _ in range(max(0, n)):
        if not piles["compra"]:
            if not piles["descarte"]:
                break
            reshuffle(piles, rng)
        card = piles["compra"].pop(0)
        piles["mao"].append(card)
        drawn.append(card)
    return drawn


def discard_hand(piles: dict) -> list[str]:
    """Descarta a mao nao guardada. Guardadas ficam (1 transicao) e a lista zera."""
    keep_budget = list(piles.get("guardadas") or [])
    kept: list[str] = []
    gone: list[str] = []
    for cid in piles["mao"]:
        if cid in keep_budget:
            keep_budget.remove(cid)
            kept.append(cid)
        else:
            gone.append(cid)
    piles["mao"] = kept
    piles["descarte"] = list(piles["descarte"]) + gone
    piles["guardadas"] = []
    return gone


def begin_round(piles: dict, rng: random.Random | None = None) -> dict:
    """Inicio de rodada do jogador (R5): descarta, compra ate `MAO_BASE`, Folego cheio."""
    discard_hand(piles)
    draw(piles, MAO_BASE - len(piles["mao"]), rng)
    piles["folego"] = FOLEGO_BASE
    piles["folego_emprestado"] = 0
    piles["pacto_carga"] = False
    return piles


def exhaust(piles: dict, card_id: str) -> bool:
    """Tira uma copia da mao e a poe em `exaurida` (R11)."""
    if card_id in piles["mao"]:
        piles["mao"].remove(card_id)
        piles["exaurida"] = list(piles["exaurida"]) + [card_id]
        return True
    return False


def play_to_pile(piles: dict, card_id: str) -> str:
    """Carta jogada sai da mao: `cena`/`descanso_*` -> exaurida; senao -> descarte (R11)."""
    card = cards.get_card(card_id) or {}
    freq = str(card.get("frequencia", "livre"))
    if card_id not in piles["mao"]:
        return ""
    if freq in ("cena", "descanso_curto", "descanso_longo"):
        exhaust(piles, card_id)
        return "exaurida"
    piles["mao"].remove(card_id)
    piles["descarte"] = list(piles["descarte"]) + [card_id]
    return "descarte"


# ==========================================================================
# Pagamento (Folego + Pacto do Abismo)
# ==========================================================================
def _plan(
    folego: int,
    emprestado: int,
    entropia: int,
    need: int,
    entropy_cost: int,
    *,
    allow_pact: bool = True,
) -> dict:
    falta = max(0, need - folego)
    plan = {
        "folego": min(need, folego),
        "emprestado": 0,
        "entropia_extra": 0,
        "ok": True,
        "motivo": "",
    }
    if falta:
        if not allow_pact:
            plan.update(ok=False, motivo=f"Fôlego insuficiente ({folego}/{need}).")
            return plan
        if emprestado + falta > PACTO_MAX_FOLEGO:
            plan.update(
                ok=False,
                motivo=f"Fôlego insuficiente ({folego}/{need}); o Pacto do Abismo "
                f"empresta no máximo {PACTO_MAX_FOLEGO} por rodada.",
            )
            return plan
        plan["emprestado"] = falta
        plan["entropia_extra"] = falta * PACTO_ENTROPIA_POR_FOLEGO
    # O Pacto GANHA Entropia (nao exige); so a Entropia propria da carta precisa estar no pool.
    if entropy_cost > entropia:
        plan.update(ok=False, motivo=f"Entropia insuficiente ({entropia}/{entropy_cost}).")
    return plan


def apply_pact(piles: dict, player: dict, plan: dict) -> None:
    """Consequencia do Pacto (todas as Posturas): +2 Entropia por Folego emprestado, pelo
    ganho generico (clamp em `max_entropy`), e +1 Carga do Abismo na 1a vez da rodada."""
    if not plan.get("emprestado"):
        return
    mx = int(player.get("max_entropy", 0) or 0)
    now = int(player.get("entropy", 0) or 0) + int(plan["entropia_extra"])
    player["entropy"] = min(mx, now) if mx > 0 else now
    if not piles.get("pacto_carga"):
        piles["pacto_carga"] = True
        player["abyss_charge"] = int(player.get("abyss_charge", 0) or 0) + 1


def pay_cost(
    piles: dict,
    player: dict,
    folego_cost: int,
    entropy_cost: int = 0,
    *,
    apply: bool = False,
    allow_pact: bool = True,
) -> dict:
    """Plano de pagamento de `folego_cost` (+ Entropia propria da carta, so validada).
    Com `apply=True` e plano ok: debita Folego e a Entropia do Pacto (a propria da carta
    e debitada por `cards.use_card`)."""
    plan = _plan(
        int(piles.get("folego", 0) or 0),
        int(piles.get("folego_emprestado", 0) or 0),
        int(player.get("entropy", 0) or 0),
        int(folego_cost),
        int(entropy_cost),
        allow_pact=allow_pact,
    )
    if apply and plan["ok"]:
        piles["folego"] = max(0, int(piles.get("folego", 0) or 0) - plan["folego"])
        piles["folego_emprestado"] = (
            int(piles.get("folego_emprestado", 0) or 0) + plan["emprestado"]
        )
    return plan


def can_pay(piles: dict, player: dict, card: dict, *, allow_pact: bool = True) -> dict:
    """`PayPlan` de uma Carta (so consulta; a mao e checada por `plan_plays`/`pay`)."""
    if card.get("injogavel") or card.get("id") == FARDO_ID:
        return {
            "folego": 0,
            "emprestado": 0,
            "entropia_extra": 0,
            "ok": False,
            "motivo": f"{card.get('name', 'Esta carta')} é um Fardo e não pode ser jogada.",
        }
    return pay_cost(
        piles,
        player,
        cards.custo_folego(card),
        cards._entropy_cost(player, card),
        allow_pact=allow_pact,
    )


def pay(piles: dict, player: dict, card: dict, *, allow_pact: bool = True) -> dict:
    plan = can_pay(piles, player, card, allow_pact=allow_pact)
    if plan["ok"]:
        pay_cost(
            piles,
            player,
            cards.custo_folego(card),
            cards._entropy_cost(player, card),
            apply=True,
            allow_pact=allow_pact,
        )
    return plan


# ==========================================================================
# Validacao de uma lista de jogadas (R7/R15) - sem efeito colateral
# ==========================================================================
def step_folego(step: Any, get_card: Callable[[str], dict | None] = cards.get_card) -> int:
    """Fôlego de uma jogada: carta -> `custo_folego`; mover/passar gratis; o resto 1."""
    kind = str(getattr(step, "kind", "pass") or "pass").lower()
    if kind in _FREE_KINDS:
        return 0
    if kind == "maneuver" and getattr(step, "maneuver", None) in _NO_COST_MANEUVERS:
        return 0
    if kind == "card":
        card = get_card(str(getattr(step, "card_id", "") or "")) or {}
        return cards.custo_folego(card) if card else 1
    return 1


def plan_plays(
    piles: dict,
    player: dict,
    plays: list[Any],
    get_card: Callable[[str], dict | None] = cards.get_card,
) -> dict:
    """Simula a lista inteira (ordem importa). Nada e gasto: devolve
    {ok, motivo, folego_total, emprestado, entropia_extra}."""
    sim = copy.deepcopy(piles)
    entropy = int(player.get("entropy", 0) or 0)
    usage = player.get("card_usage") or {}
    played_turn: set[str] = set()
    total = {"folego_total": 0, "emprestado": 0, "entropia_extra": 0}
    for step in plays:
        kind = str(getattr(step, "kind", "pass") or "pass").lower()
        cost = step_folego(step, get_card)
        entropy_cost = 0
        card: dict | None = None
        if kind == "card":
            cid = str(getattr(step, "card_id", "") or "")
            card = FARDO_CARD if cid == FARDO_ID else get_card(cid)
            virtue = {vc.get("card_id") for vc in (player.get("virtue_cards") or [])}
            if card is None:
                return {"ok": False, "motivo": f"Carta '{cid}' desconhecida.", **total}
            if card.get("injogavel") or cid == FARDO_ID:
                return {
                    "ok": False,
                    "motivo": f"{card.get('name', 'Esta carta')} é um Fardo e não pode ser jogada.",
                    **total,
                }
            if cid in virtue and cid not in sim["mao"]:
                pass  # Carta de Virtude e talento permanente: nao vem da mao
            elif cid not in sim["mao"]:
                return {
                    "ok": False,
                    "motivo": f"{card.get('name', cid)} não está na sua mão.",
                    **total,
                }
            freq = str(card.get("frequencia", "livre"))
            counter = cards.FREQ_COUNTER.get(freq)
            if counter == "used_this_turn":
                if cid in played_turn:
                    return {
                        "ok": False,
                        "motivo": f"'{card.get('name', cid)}' só pode ser jogada 1× por rodada.",
                        **total,
                    }
            elif counter and int((usage.get(cid) or {}).get(counter, 0) or 0) >= 1:
                return {
                    "ok": False,
                    "motivo": f"'{card.get('name', cid)}' já foi usada (1×{freq}).",
                    **total,
                }
            entropy_cost = cards._entropy_cost(player, card)
        plan = _plan(
            int(sim.get("folego", 0) or 0),
            int(sim.get("folego_emprestado", 0) or 0),
            entropy,
            cost,
            entropy_cost,
        )
        if not plan["ok"]:
            return {"ok": False, "motivo": plan["motivo"], **total}
        sim["folego"] = max(0, int(sim["folego"]) - plan["folego"])
        sim["folego_emprestado"] = int(sim["folego_emprestado"]) + plan["emprestado"]
        entropy -= entropy_cost
        mx = int(player.get("max_entropy", 0) or 0)
        entropy = (
            min(mx, entropy + plan["entropia_extra"])
            if mx > 0
            else entropy + plan["entropia_extra"]
        )
        total["folego_total"] += cost
        total["emprestado"] += plan["emprestado"]
        total["entropia_extra"] += plan["entropia_extra"]
        if card is not None:
            cid = str(card.get("id"))
            if cid in sim["mao"]:
                play_to_pile(sim, cid)
            played_turn.add(cid)
    return {"ok": True, "motivo": "", **total}


# ==========================================================================
# Visao publica (API) - nunca a ordem do monte
# ==========================================================================
def public_view(piles: dict | None) -> dict | None:
    if not isinstance(piles, dict):
        return None
    hand = []
    for cid in piles.get("mao") or []:
        card = FARDO_CARD if cid == FARDO_ID else (cards.get_card(cid) or {})
        hand.append(
            {
                "id": cid,
                "name": card.get("name", cid),
                "tipo": card.get("tipo"),
                "custo_folego": 0 if cid == FARDO_ID else cards.custo_folego(card),
                "custo_entropia": int(card.get("custo_entropia", 0) or 0),
                "jogavel": cid != FARDO_ID,
            }
        )
    return {
        "mao": hand,
        "compra": len(piles.get("compra") or []),
        "descarte": len(piles.get("descarte") or []),
        "exaurida": len(piles.get("exaurida") or []),
        "folego": int(piles.get("folego", 0) or 0),
        "folego_max": FOLEGO_BASE,
        "folego_emprestado": int(piles.get("folego_emprestado", 0) or 0),
        "pacto_max": PACTO_MAX_FOLEGO,
    }
