"""SPEC-347 R5.1: a ordem de lados exibida (`out["initiative"]`) é a ordem real em que a rodada resolveu os turnos."""

from __future__ import annotations

import random

import pytest

from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_turn as ct


def _world():
    scene = cs.new_scene()
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
        },
        is_player=True,
    )
    enemy = orch.ensure_combat_sheet(
        {
            "id": "enemy_1",
            "name": "Saqueador",
            "categoria": "padrao",
            "max_vitalidade": 12,
            "vitalidade": 12,
            "virtudes": {"forca": 3, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
        }
    )
    for i in ("player", "enemy_1"):
        cs.place(scene, i)
    cs.freeze(scene)
    return (
        scene,
        {"player": player, "enemy_1": enemy},
        {"hero": ["player"], "ally": [], "enemy": ["enemy_1"]},
    )


def _first_side_by_turns(turns: list[str]) -> list[str]:
    order: list[str] = []
    for actor in turns:
        side = "heroes" if actor == "player" else "enemy"
        if side not in order:
            order.append(side)
    return order


@pytest.mark.parametrize("initiator", [None, "enemy", "heroes"])
@pytest.mark.parametrize("seed", range(6))
def test_order_matches_resolved_turns(seed, initiator):
    scene, actors, sides = _world()
    decl = {"player": ct.TurnDeclaration(actor_id="player", acao=ct.TurnStep(kind="pass"))}
    out = orch.run_round(
        scene, actors, sides, {}, declarations=decl, rng=random.Random(seed), initiator=initiator
    )
    assert out["initiative"], "a rodada precisa gravar a iniciativa"
    assert out["initiative"] == _first_side_by_turns(out["resolved_turns"])
