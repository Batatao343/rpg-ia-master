"""SPEC-373 R12: na ação extra do chefe com `on`, só Carta própria; `off` não muda."""

from __future__ import annotations

import json
import random

import pytest

from agents.bestiary import load_bestiary
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import enemy_decks as edk

BOSS = "mon_borda_que_anda"


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_DECKS", raising=False)
    edk.reload()
    yield
    edk.reload()


def _boss():
    entry = json.loads(json.dumps(load_bestiary()[BOSS]))
    return orch.ensure_combat_sheet({**entry, "id": f"{BOSS}_1"})


def _player():
    return orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Herói",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
            "entropy": 10,
            "max_entropy": 10,
            "abyss_charge": 0,
        },
        is_player=True,
    )


def _declared_decks(monkeypatch) -> list[list[str]]:
    boss = _boss()
    scene = cs.new_scene()
    for i in ("player", boss["id"]):
        cs.place(scene, i)
    cs.freeze(scene)
    actors = {"player": _player(), boss["id"]: boss}
    sides = {"hero": ["player"], "ally": [], "enemy": [boss["id"]]}
    seen: list[list[str]] = []
    real = orch.enemy_declaration

    def spy(scene_, eid, actors_, sides_, **kw):
        if eid != "player":
            seen.append(list(actors_[eid]["cartas"]))
        return real(scene_, eid, actors_, sides_, **kw)

    monkeypatch.setattr(orch, "enemy_declaration", spy)
    orch.run_round(scene, actors, sides, {"player": actors["player"]}, rng=random.Random(2))
    # restaurado depois da declaração (a fase pode ter somado Cartas, nunca tirado)
    assert set(_boss()["cartas"]) <= set(actors[boss["id"]]["cartas"])
    return seen


def test_extra_nunca_declara_familia_ou_faccao_com_on(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    full = _boss()["cartas"]
    own = set(load_bestiary()[BOSS]["cartas_autorais"])
    assert set(full) - own, "o chefe precisa ter Carta de família/facção para o teste valer"
    seen = _declared_decks(monkeypatch)
    assert len(seen) == 2
    assert set(seen[0]) - own  # a 1ª ação pode jogar a Carta de família
    assert set(seen[1]) <= own  # a extra só joga própria


def test_off_declaracao_igual_nas_duas_acoes(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_DECKS", "off")
    seen = _declared_decks(monkeypatch)
    assert len(seen) == 2 and seen[0] == seen[1]


def test_sem_filtro_quando_nao_ha_o_que_tirar():
    assert edk.extra_action_cards({"cartas": ["a"], "cartas_autorais": ["a"]}) is None
