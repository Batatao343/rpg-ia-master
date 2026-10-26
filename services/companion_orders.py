"""services/companion_orders.py - ordens do jogador a companheiros (SPEC-325 R15, D9).

Funcoes puras, sem LLM. As restricoes saem de uma TABELA FIXA sobre os valores da alma
(SPEC-300); `tactical_profile.validate_companion_order` decide se a ordem e aceita. Recusa
nunca derruba o turno: o aliado age pelo perfil e a ordem so vira log.
"""

from __future__ import annotations

from services import tactical_profile as tp
from services.conflict_turn import TurnDeclaration, TurnStep

# (eixo de valor, patamar, tag bloqueada, resistencia, motivo)
RESTRICTION_TABLE: tuple[tuple[str, int, str, str, str], ...] = (
    ("honra", 2, "atacar_rendido", "absoluta", "não ataca quem já se rendeu"),
    ("compaixao", 2, "atacar_incapacitado", "resistente", "não golpeia quem está caído"),
    ("coragem", 2, "abandonar_posto", "resistente", "não abandona o posto"),
)


def restrictions_from_soul(soul: dict | None) -> list[dict]:
    """Prioridades `restricao` do perfil tatico derivadas dos valores da alma (D9)."""
    values = (soul or {}).get("values") or {}
    out: list[dict] = []
    for axis, floor, tag, resistance, reason in RESTRICTION_TABLE:
        try:
            level = int(values.get(axis, 0) or 0)
        except (TypeError, ValueError):
            continue
        if level >= floor:
            out.append(
                {
                    "trigger": "sempre",
                    "tipo": "restricao",
                    "action_key": "attack",
                    "action_hint": reason,
                    "resistance": resistance,
                    "blocks": [tag],
                }
            )
    return out


def validate_order(ally: dict, soul: dict | None, order: dict) -> dict:
    """`validate_companion_order` com as restricoes da alma somadas ao perfil do aliado.
    `leverage` = aprovacao >= LOYAL_AT (lealdade vence a Restricao Resistente)."""
    from services.companion_soul import LOYAL_AT

    profile = dict(ally.get("tactical_profile") or {})
    profile["priorities"] = [*(profile.get("priorities") or []), *restrictions_from_soul(soul)]
    leverage = int((soul or {}).get("approval", 0) or 0) >= LOYAL_AT
    probe = {"tactical_profile": profile}
    return tp.validate_companion_order(probe, {**order, "leverage": leverage})


def _alive(actor: dict | None) -> bool:
    return bool(actor) and not actor.get("dead") and actor.get("status", "ativo") == "ativo"


def ally_declaration(
    order: dict, ally: dict, scene: dict, actors_by_id: dict, sides: dict
) -> TurnDeclaration | None:
    """`TurnDeclaration` do aliado para a ordem, ou None quando nao ha alvo/ato valido
    (o aliado age pelo perfil)."""
    ally_id = str(order.get("ally_id") or "")
    if not ally_id or not _alive(ally) or ally_id not in set(sides.get("ally", [])):
        return None
    verb = order.get("verb")
    hostile = [e for e in sides.get("enemy", []) if _alive(actors_by_id.get(e))]
    friendly = [*sides.get("hero", []), *sides.get("ally", [])]
    if verb == "atacar":
        target = order.get("target_id")
        if target is None and hostile:
            target = hostile[0]
        if target not in hostile:
            return None
        return TurnDeclaration(
            actor_id=ally_id, acao=TurnStep(kind="attack", target_id=str(target))
        )
    if verb == "recuar":
        return TurnDeclaration(actor_id=ally_id, acao=TurnStep(kind="move", direction="afastar"))
    if verb == "proteger":
        others = [f for f in friendly if f != ally_id and _alive(actors_by_id.get(f))]
        hero = next(iter(sides.get("hero", [])), None)
        target = hero if hero in others else (others[0] if others else None)
        if target is None:
            return None
        return TurnDeclaration(
            actor_id=ally_id, acao=TurnStep(kind="tactic", maneuver="protect", target_id=target)
        )
    if verb == "curar":
        others = [f for f in friendly if f != ally_id and _alive(actors_by_id.get(f))]

        def ratio(fid: str) -> float:
            a = actors_by_id[fid]
            maximum = int(a.get("max_vitalidade", 0) or 0) or 1
            return int(a.get("vitalidade", maximum) or 0) / maximum

        if not others:
            return None
        target = min(others, key=lambda f: (ratio(f), f))
        return TurnDeclaration(
            actor_id=ally_id, acao=TurnStep(kind="tactic", maneuver="support", target_id=target)
        )
    return None
