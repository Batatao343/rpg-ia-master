"""SPEC-325 R9 - regex fechada do golpe nao-letal (com negacao e falso-positivo)."""

import pytest

from services.combat_intents import nonlethal_declared


@pytest.mark.parametrize(
    "text",
    [
        "derrubo o soldado sem matar",
        "Quero NOCAUTEAR o guarda",
        "tento desacordar o bandido",
        "vou poupar o chefe",
        "golpe não letal no lobo",
        "ataco com golpe nao-letal",
        "derrubo ele e deixo vivo",
    ],
)
def test_positive(text):
    assert nonlethal_declared(text)


@pytest.mark.parametrize(
    "text",
    [
        "não vou poupar ninguém",
        "nunca vou nocautear esse canalha",
        "ataco o goblin",
        "mato o soldado",
        "",
    ],
)
def test_negative_and_negation(text):
    assert not nonlethal_declared(text)
