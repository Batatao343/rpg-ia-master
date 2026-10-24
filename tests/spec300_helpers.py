"""Helpers compartilhados dos testes da SPEC-300 (estado mínimo com Brunna recrutada)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from services import companion_soul as cs

BRUNNA = "Brunna Ponte-Alta"
BRUNNA_ID = "npc_mv_brunna_ponte_alta"


def npc(traits=(), rel=7, **extra) -> dict:
    return {
        "id": BRUNNA_ID,
        "name": BRUNNA,
        "role": "engenheira das passagens anãs",
        "relationship": rel,
        "hidden_traits": list(traits),
        "revealed_traits": [],
        "faction": "ultimos_anoes_reino",
        "home_location_id": "montanhas_afiadas",
        "in_scene": True,
        "interaction_count": 3,
        **extra,
    }


def comp(**extra) -> dict:
    return {
        "id": BRUNNA_ID,
        "name": BRUNNA,
        "origin_npc": BRUNNA_ID,
        "archetype": "guerreiro",
        "active": True,
        "waiting_at": "",
        "status": "ativo",
        "vitalidade": 6,
        "max_vitalidade": 6,
        **extra,
    }


def make_state(
    *,
    traits=(),
    turn=10,
    day=3,
    text="Sigo em frente.",
    events=(),
    baseline_events=(),
    party=True,
    souls=None,
    gold=100,
    quests=(),
    location="montanhas_afiadas",
    combat=None,
    ack=(),
    approval=None,
    **extra,
) -> dict:
    state = {
        "game_id": "g300",
        "player": {"name": "Hero", "gold": gold, "abyss_charge": 0},
        "world": {
            "turn_count": turn,
            "current_location_id": location,
            "world_clock": {"day": day, "period": "manha"},
        },
        "npcs": {BRUNNA: npc(traits)},
        "party": [comp()] if party else [],
        "messages": [HumanMessage(content=text)],
        "event_log": list(events),
        "turn_baseline": {
            "gold": gold,
            "abyss_charge": 0,
            "event_ids": list(baseline_events),
            "turn": turn,
        },
        "quests": list(quests),
        "factions": [],
        "combat": combat,
        "companion_voice_ack": list(ack) or None,
        "last_interaction_outcome": {},
    }
    state.update(extra)
    if souls is not None:
        state["companion_souls"] = souls
    elif party:
        soul = cs.ensure_soul(state, state["party"][0])
        if approval is not None:
            soul["approval"] = approval
        state["companion_souls"] = {BRUNNA_ID: soul}
    return state


def ev(event_id, etype, target="", actor="player", **payload) -> dict:
    return {
        "event_id": event_id,
        "type": etype,
        "actor_id": actor,
        "target_id": target,
        "payload": payload,
        "turn": 10,
        "source": "test",
    }


def merged(state: dict, updates: dict) -> dict:
    return {**state, **updates}
