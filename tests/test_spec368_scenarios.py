"""SPEC-368 R13 - cada situacao do §6 e alcancavel offline pelas fixtures de cenario."""

from __future__ import annotations

import pytest

from tests.fixtures import spec368_scenarios as sc368

ITEMS = sorted(sc368.BUILDERS)


def test_every_item_of_the_smoke_has_a_scenario():
    assert ITEMS == list(range(1, 15))  # os 14 itens do §6, sem lacuna


@pytest.mark.parametrize("item", ITEMS)
def test_scenario_reaches_the_situation(item):
    scenario = sc368.get(item)
    assert scenario.item == item and scenario.spec and scenario.passos
    assert scenario.problems() == [], scenario.descricao


def test_scenarios_are_deterministic():
    a, b = sc368.get(12), sc368.get(12)
    assert a.data["combat"]["piles"]["mao"] == b.data["combat"]["piles"]["mao"]
    assert a.data["combat"]["piles"]["compra"] == b.data["combat"]["piles"]["compra"]


def test_building_scenarios_does_not_leak_env():
    import os

    before = {k: os.environ.get(k) for k in sc368.CARDS_ON}
    sc368.build_all()
    assert {k: os.environ.get(k) for k in sc368.CARDS_ON} == before
