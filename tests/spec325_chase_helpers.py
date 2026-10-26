"""Helpers da SPEC-325 Fase B: fuga/abandono/sacrificio pelo `combat_node` real."""

from __future__ import annotations

import random

from langchain_core.messages import HumanMessage

from agents import combat as cbt
from tests.spec300_helpers import BRUNNA, BRUNNA_ID
from tests.spec300_helpers import make_state as soul_state
from tests.spec325_helpers import lacaio
from tests.spec325_helpers import make_state as combat_state

__all__ = ["BRUNNA", "BRUNNA_ID", "chaser", "first_state", "narration_spy", "step"]


def chaser(**over) -> dict:
    """Perseguidor resistente e inofensivo (nao morre nem acerta nas rodadas de teste)."""
    return lacaio(
        tactical_profile={"pursuit_policy": "persegue", "priorities": []},
        hp=30,
        max_hp=30,
        vitalidade=30,
        max_vitalidade=30,
        **over,
    )


def first_state(*, party: bool = False, approval=None, traits=(), day: int = 3, enemies=None):
    """Estado do 1o turno de combate (a cena nasce no nó). `party=True` recruta a Brunna."""
    base = combat_state(enemies or [chaser()], "fujo")
    if party:
        s = soul_state(traits=traits, day=day, approval=approval)
        base.update(
            party=s["party"],
            npcs=s["npcs"],
            companion_souls=s["companion_souls"],
            quests=[],
            factions=[],
            event_log=[],
        )
        base["world"] = dict(s["world"])
    return base


def narration_spy():
    """`narrate` falso que guarda TUDO o que iria ao narrador."""
    seen: list[str] = []

    def fake(*args, **kwargs):
        seen.append(repr((args, kwargs)))
        return "Fim."

    return fake, seen


def step(state, res, monkeypatch, intent, *, declaration=None, seed=1, narrate=None):
    """Mescla o resultado do nó no estado e roda a próxima rodada."""
    merged = {**state, **{k: v for k, v in res.items() if k != "next"}}
    merged["messages"] = [HumanMessage(content=intent)]
    merged["combat_declaration"] = declaration
    monkeypatch.setattr(cbt, "_narrate", narrate or (lambda *a, **k: "Fim."))
    random.seed(seed)
    return merged, cbt.combat_node(merged)
