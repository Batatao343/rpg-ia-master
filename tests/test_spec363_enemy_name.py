"""SPEC-363 R29/R30: família pelo registro do bestiário; nome sem cabeça genérica."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import AIMessage, SystemMessage

import agents.combat as combat
from services import creature_art
from services import encounter_manifest as em
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state


def test_family_from_bestiary_record():
    assert creature_art.family_of({"id": "enemy_goblin_1", "name": "Goblin"}) == "bruto"
    assert creature_art.family_of({"id": "enemy_goblin", "name": "Goblin", "arquetipo": "bruto"}) == "bruto"
    assert creature_art.family_of({"id": "nao_existe_9", "name": "Nada"}) == "desconhecida"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Criatura da Fogueira", True),
        ("Vulto do Poço", True),
        ("A criatura além das estacas", True),
        ("Goblin", False),
        ("Criatura", False),
        ("Lobo da Fogueira", False),
    ],
)
def test_generic_head_detected(name, expected):
    assert em.has_generic_head(name) is expected


def test_generic_head_name_rejected(monkeypatch):
    random.seed(5)
    _install_llm(monkeypatch, scan=_scan(("Criatura da Fogueira", 1)))
    monkeypatch.setattr(
        combat,
        "generate_new_enemy",
        lambda name, **k: {
            "id": "enemy_" + name.lower().replace(" ", "_") + "_1",
            "name": name,
            "type": "padrao",
            "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
        },
    )
    state = _start_state(
        messages=[
            AIMessage(content="Algo ronda a fogueira."),
            SystemMessage(content="SYSTEM: COMBAT START. TARGET_HINT: a criatura"),
        ]
    )
    enemies, _ = combat._spawn_v4_enemies(state["messages"], "a criatura", state)
    assert enemies
    for e in enemies:
        assert not em.has_generic_head(e["name"]), e["name"]
