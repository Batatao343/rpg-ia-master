"""services/card_deck_round.py - ponte entre `run_round` e o Baralho de Conflito (SPEC-328).

Isolado de proposito: `run_round` so chama 3 ganchos (`refusal`, `shadow`,
`resolve_player_plays`), todos atras de `RPG_CARD_DECK`. Sem `state["_piles"]` o
motor e o de antes, byte a byte (combate antigo sem `pilhas` segue no modo atual).

`state` aqui e o `round_state` do no de combate:
    {"player": ficha, "_piles": combat["pilhas"], "_deck_mode": "on"|"shadow"}
"""

from __future__ import annotations

import logging

from services import card_piles, cards
from services import conflict_turn as ct

logger = logging.getLogger("rpg.conflict")


def deck_mode(state: dict | None) -> str:
    """ "on" | "shadow" | "" - so vale com pilhas presentes (R16)."""
    if not isinstance(state, dict) or not isinstance(state.get("_piles"), dict):
        return ""
    m = str(state.get("_deck_mode") or "")
    return m if m in ("on", "shadow") else ""


def _plays(declarations: dict, player_id: str | None) -> list:
    decl = declarations.get(player_id) if player_id else None
    if decl is None:
        return []
    if not isinstance(decl, ct.TurnDeclaration):
        decl = ct.TurnDeclaration(**decl)
    return decl.plays()


def refusal(state, actors_by_id, player_id, declarations) -> str:
    """R7/R15 (modo `on`): lista invalida -> rejeicao explicada, nada e gasto."""
    if deck_mode(state) != "on":
        return ""
    plays = _plays(declarations, player_id)
    player = actors_by_id.get(player_id) if player_id else None
    if not plays or player is None:
        return ""
    plan = card_piles.plan_plays(state["_piles"], player, plays)
    return "" if plan["ok"] else str(plan["motivo"])


def shadow(state, actors_by_id, player_id, declarations, out: dict) -> None:
    """R17 (modo `shadow`): calcula o plano e registra no trace; nao muda nada."""
    if deck_mode(state) != "shadow":
        return
    plays = _plays(declarations, player_id)
    player = actors_by_id.get(player_id) if player_id else None
    if not plays or player is None:
        return
    plan = card_piles.plan_plays(state["_piles"], player, plays)
    out["deck_shadow"] = {
        "ok": bool(plan["ok"]),
        "motivo": plan["motivo"],
        "folego_total": plan["folego_total"],
        "emprestado": plan["emprestado"],
        "plays": len(plays),
    }
    try:
        from services import mechanics_trace as _mt

        _mt.record_step(
            "deck_shadow",
            actor=player_id,
            result="ok" if plan["ok"] else "reject",
            amount=plan["folego_total"],
            reason=plan["motivo"] or None,
        )
    except Exception:  # trace nunca derruba o turno
        logger.debug("deck_shadow trace failed", exc_info=True)


def resolve_player_plays(
    scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng
) -> None:
    """R7: cada jogada resolve em sequencia no mesmo `_resolve_actor_turn`, pagando
    Folego (e Pacto) antes. Pre/pos de movimento ficam na 1a/ultima jogada."""
    from services import conflict_orchestrator as orch

    piles = state["_piles"]
    decl = decl if isinstance(decl, ct.TurnDeclaration) else ct.TurnDeclaration(**decl)
    plays = decl.plays()
    if not plays:
        orch._resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, decl, state, out, rng)
        return
    last = len(plays) - 1
    carry_guard = False
    for i, step in enumerate(plays):
        if i and not orch._can_act(actor):
            break
        sub = ct.TurnDeclaration(
            actor_id=decl.actor_id,
            pre_acao=decl.pre_acao if i == 0 else None,
            acao=step,
            pos_acao=decl.pos_acao if i == last else None,
            reaction_card_id=decl.reaction_card_id,
        )
        kind = str(step.kind or "pass").lower()
        card = cards.get_card(step.card_id or "") if kind == "card" else None
        cost = card_piles.step_folego(step)
        snap = (
            int(actor.get("entropy", 0) or 0),
            int(actor.get("abyss_charge", 0) or 0),
            bool(piles.get("pacto_carga")),
        )
        plan = {"folego": 0, "emprestado": 0, "entropia_extra": 0, "ok": True, "motivo": ""}
        if cost:
            plan = card_piles.pay_cost(
                piles,
                actor,
                cost,
                cards._entropy_cost(actor, card) if card else 0,
                apply=True,
            )
            if not plan["ok"]:  # estado mudou no meio da rodada: pula, sem custo
                out["logs"].append(plan["motivo"])
                continue
        if plan["emprestado"]:
            card_piles.apply_pact(piles, actor, plan)
            out["logs"].append(
                f"Pacto do Abismo: você toma {plan['emprestado']} Fôlego emprestado; "
                f"o Abismo empresta, e cobra: +{plan['entropia_extra']} Entropia e Carga."
            )
            orch._record_class_event(
                out,
                "pacto_abismo",
                emprestado=plan["emprestado"],
                entropia_extra=plan["entropia_extra"],
            )
        used_before = len(out.get("cards_used") or [])
        orch._resolve_actor_turn(scene, actor, actor_id, actors_by_id, sides, sub, state, out, rng)
        if carry_guard:  # P2-2: `resolve_turn` zera a Guarda a cada jogada; ela dura a rodada
            _restore_guard(scene, actor_id)
        carry_guard = _guarding(scene, actor_id)
        if kind == "card" and card is not None:
            used = any(
                u.get("actor_id") == actor_id and u.get("card_id") == step.card_id
                for u in (out.get("cards_used") or [])[used_before:]
            )
            if used:
                card_piles.play_to_pile(piles, str(step.card_id))
            elif cost:
                # a Carta nao resolveu (ex.: Entropia propria insuficiente): desfaz TUDO
                piles["folego"] = int(piles.get("folego", 0) or 0) + plan["folego"]
                piles["folego_emprestado"] = max(
                    0, int(piles.get("folego_emprestado", 0) or 0) - plan["emprestado"]
                )
                actor["entropy"], actor["abyss_charge"], piles["pacto_carga"] = snap
    seen = False
    deduped: list = []
    for turn_id in out.get("resolved_turns") or []:
        if turn_id == actor_id:
            if seen:
                continue
            seen = True
        deduped.append(turn_id)
    out["resolved_turns"] = deduped


def _guarding(scene, actor_id) -> bool:
    from services import conflict_scene as cs

    pos = cs._pos(scene, actor_id)
    return bool(pos and pos.get("guarding"))


def _restore_guard(scene, actor_id) -> None:
    from services import conflict_scene as cs

    pos = cs._pos(scene, actor_id)
    if pos is not None:
        pos["guarding"] = True


def reaction_gate(state, reactor, card) -> bool | None:
    """R12: reacao do jogador sai da MAO e paga o Folego que sobrou (sem Pacto).
    None = sem baralho ativo (regra de antes); True/False = pode / nao pode."""
    if deck_mode(state) != "on":
        return None
    piles = state["_piles"]
    if str(card.get("id")) not in piles["mao"]:
        return False
    return bool(card_piles.can_pay(piles, reactor, card, allow_pact=False)["ok"])


def reaction_commit(state, reactor, card) -> None:
    if deck_mode(state) != "on":
        return
    piles = state["_piles"]
    card_piles.pay(piles, reactor, card, allow_pact=False)
    card_piles.play_to_pile(piles, str(card.get("id")))
