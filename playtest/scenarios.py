"""Cenários dirigidos do playtest: pré-condição + ação + oráculo fechados.

Eles não entram em ``PROFILES``/``--all``. O objetivo é provar uma vertical
específica sem esperar que a simulação sorteie NPC ou mercador adequados.
"""
from __future__ import annotations

import copy
from typing import Optional

from playtest.profiles import ProfileDecision

RECRUIT_NPC_NAME = "Brunna Ponte-Alta"
RECRUIT_NPC_ID = "npc_mv_brunna_ponte_alta"
TRADE_START_GOLD = 200

_SCENARIOS = {
    "recrutamento": "recrutador",
    "comercio": "comerciante",
}


def names() -> tuple[str, ...]:
    return tuple(_SCENARIOS)


def profile_for(name: str) -> str:
    try:
        return _SCENARIOS[str(name)]
    except KeyError as exc:
        raise KeyError(
            f"cenário desconhecido: {name!r} (conhecidos: {sorted(_SCENARIOS)})"
        ) from exc


def _move_world(world: dict, location_id: str) -> dict:
    from gamedata import get_location

    location = get_location(location_id)
    if not location:
        raise KeyError(f"local canônico ausente: {location_id}")
    moved = copy.deepcopy(world or {})
    moved["current_location_id"] = location_id
    moved["current_location"] = location["name"]
    moved["danger_level"] = int(location.get("danger", 1) or 1)
    visited = list(moved.get("visited") or [])
    if location_id not in visited:
        visited.append(location_id)
    moved["visited"] = visited
    return moved


def prepare(name: str, state: dict) -> dict:
    """Devolve cópia do estado com pré-condições mecânicas do cenário."""
    profile_for(name)  # valida catálogo
    prepared = copy.deepcopy(dict(state or {}))
    if name == "recrutamento":
        prepared["world"] = _move_world(
            prepared.get("world") or {}, "montanhas_afiadas",
        )
        npcs = copy.deepcopy(prepared.get("npcs") or {})
        npcs[RECRUIT_NPC_NAME] = {
            "id": RECRUIT_NPC_ID,
            "name": RECRUIT_NPC_NAME,
            "persona": (
                "Guia veterana das passagens móveis; direta, leal e avessa a "
                "promessas vazias."
            ),
            "relationship": 10,
            "in_scene": True,
            "known_by_player": True,
            "home_location_id": "montanhas_afiadas",
            "location": "Montanhas Afiadas",
            "traits": [],
            "memory": [],
        }
        prepared["npcs"] = npcs
        prepared["party"] = [
            ally for ally in (prepared.get("party") or [])
            if str(ally.get("name") or "") != RECRUIT_NPC_NAME
        ]
        return prepared

    prepared["world"] = _move_world(
        prepared.get("world") or {}, "na_anel_dourado",
    )
    player = copy.deepcopy(prepared.get("player") or {})
    player["gold"] = TRADE_START_GOLD
    player["inventory"] = [
        item for item in (player.get("inventory") or [])
        if str(item.get("id") or "") != "pocao_cura"
    ]
    prepared["player"] = player
    return prepared


def decision_for(name: str, turn: int, state: dict) -> Optional[ProfileDecision]:
    """A primeira ação é inequívoca; turnos extras voltam ao perfil normal."""
    profile_for(name)
    if int(turn) != 1:
        return None
    if name == "recrutamento":
        return ProfileDecision(
            text=(
                f"Peço que {RECRUIT_NPC_NAME} se junte a mim na jornada e "
                "venha comigo."
            ),
            mode="free_text",
        )
    return ProfileDecision(
        text="Compro uma Poção de Cura Menor no Empório do Anel Dourado.",
        mode="free_text",
    )


def _violation(check_id: str, message: str, turn: int) -> dict:
    return {
        "check_id": check_id,
        "severity": "error",
        "turn": int(turn),
        "message": message,
        "details": {"scenario": check_id.split(".", 1)[-1]},
    }


def oracle_violations(name: str, result) -> list[dict]:
    """Pós-condição observável que transforma smoke inconclusivo em falha."""
    profile_for(name)
    state = getattr(result, "final_state", {}) or {}
    turn = int(getattr(result, "turns_completed", 0) or 0)
    if name == "recrutamento":
        import party

        if any(
            str(ally.get("name") or "") == RECRUIT_NPC_NAME
            for ally in party.active_allies(state)
        ):
            return []
        return [_violation(
            "smoke.recruitment_not_observed",
            f"{RECRUIT_NPC_NAME} não entrou na party ativa.",
            turn,
        )]

    player = state.get("player") or {}
    has_potion = any(
        str(item.get("id") or "") == "pocao_cura"
        and int(item.get("qty", 0) or 0) >= 1
        for item in (player.get("inventory") or [])
        if isinstance(item, dict)
    )
    spent_gold = int(player.get("gold", TRADE_START_GOLD) or 0) < TRADE_START_GOLD
    if has_potion and spent_gold:
        return []
    return [_violation(
        "smoke.trade_not_observed",
        "Compra dirigida não reduziu ouro e adicionou poção ao inventário.",
        turn,
    )]
