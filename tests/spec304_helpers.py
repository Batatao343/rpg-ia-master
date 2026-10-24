"""Helpers compartilhados dos testes da SPEC-304 (NPCs off-screen).

`step` imita o que o storyteller + arquivista fazem num turno que vira dias: tick do motor,
mescla do `state_patch`, percepção (ledger + crença) e processamento da fila de eventos.
"""

from __future__ import annotations

import os

from services import event_processor as ep
from services import npc_world
from services import world_engine as we
from tests.spec300_helpers import BRUNNA, BRUNNA_ID, comp, make_state, npc

__all__ = [
    "BRUNNA",
    "BRUNNA_ID",
    "comp",
    "hook",
    "known_npc",
    "make_state",
    "npc",
    "setup_env",
    "step",
    "waiting_state",
]


def setup_env(monkeypatch, npc_mode: str = "on") -> None:
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_WORLD", npc_mode)
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def world_at(day: int, loc: str, period: str = "Manhã") -> dict:
    return {
        "world_clock": {"day": day, "period": period},
        "turn_count": day,
        "current_location_id": loc,
    }


def waiting_state(
    *, at: str = "ma_saidas_baixas", player_at: str = "nova_arcadia", day: int = 1, **extra
) -> dict:
    """Brunna deixada esperando em `at`; o jogador está em `player_at`."""
    import gamedata

    st = make_state(
        location=player_at,
        day=day,
        party=True,
        factions=gamedata.seed_factions(),
        event_log=[],
        world_projection={},
        **extra,
    )
    st["party"] = [comp(active=False, waiting_at=at)]
    st["world"] = {**st["world"], **world_at(day, player_at)}
    st["npcs"][BRUNNA]["in_scene"] = False
    return st


def step(
    state: dict, d0: int, d1: int, loc: str | None = None, *, perceive: bool = True, intel=None
) -> we.WorldTickResult:
    """Um turno que vira `d0 -> d1` com o jogador terminando em `loc`."""
    loc = loc or state["world"].get("current_location_id", "nova_arcadia")
    before, after = world_at(d0, state["world"]["current_location_id"]), world_at(d1, loc)
    res = we.advance_days(state, before, after, state["factions"], intel or {})
    state["world"] = {**state["world"], **after}
    if res.world_sim is not None:
        state[res.sim_key] = res.world_sim
    for k, v in (res.state_patch or {}).items():
        state[k] = v
    pending = list(state.get("pending_world_events") or []) + list(res.pending_events)
    seen: list = []
    if perceive and res.world_sim is not None and res.sim_key == "world_sim":
        from agents import storyteller as st_mod

        world, seen = st_mod._perceive_world(state, state["world"], state["factions"], {}, res)
        state["world"] = world
        state["world_sim"] = res.world_sim
        state.setdefault("_seen", []).extend(seen)
    if npc_world.mode() == "on":
        beliefs, learned = npc_world.on_perceived(state, seen)
        state["npc_beliefs"] = beliefs
        pending += learned
    state["pending_world_events"] = pending
    updates = ep.process_pending_events(state)
    state.update(updates)
    return res


def clear_env() -> None:
    for k in ("RPG_WORLD_ENGINE", "RPG_NPC_WORLD", "RPG_NPC_KNOWLEDGE"):
        os.environ.pop(k, None)


def hook(state: dict, day: int, *, events=(), sim: dict | None = None):
    """Roda SO o hook de NPCs num dia (sem o resto do tick) e mescla o patch no estado."""
    sim = (
        sim or state.get("world_sim") or we._new_sim(state["game_id"], day, state["factions"], "on")
    )
    state["world_sim"] = sim
    ctx = we.DayContext(
        state["game_id"],
        day,
        sim,
        state.setdefault("world_projection", {}),
        state["world"],
        state["factions"],
        None,
        state=state,
        events=list(events),
    )
    res = npc_world.day_hook(ctx)
    for k, v in (res.state_patch or {}).items():
        state[k] = v
    return res


def known_npc(ref: str, name: str, rel: int = 5, **extra) -> dict:
    return {
        "id": ref,
        "name": name,
        "role": "viajante",
        "relationship": rel,
        "home_location_id": "nova_arcadia",
        "known_by_player": True,
        "hidden_traits": [],
        "revealed_traits": [],
        **extra,
    }
