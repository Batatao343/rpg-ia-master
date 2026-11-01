"""SPEC-355 R17: qualquer Carta `buff_iniciativa` no baralho anula a emboscada."""

from __future__ import annotations

import pytest

from agents import combat

CARTAS = [
    "dev_zel_vigilia",
    "arc_imp_remendo",
    "arc_equacao_persistente",
    "med_dose_choque",
    "san_conta_memorizada",
]
WORLD = {"encounter_surprise": "enemy"}


@pytest.mark.parametrize("cid", CARTAS)
def test_buff_iniciativa_card_negates_ambush(cid):
    player = {"deck": ["bas_san_golpe", cid]}
    assert combat._has_vigilia(player)
    assert combat._opening_initiator(WORLD, "", player)[0] is None
    assert combat._opening_initiator(WORLD, "", {"prepared_cards": [cid]})[0] is None


def test_no_buff_iniciativa_keeps_ambush():
    player = {"deck": ["bas_san_golpe", "bas_san_guarda"], "prepared_cards": []}
    assert not combat._has_vigilia(player)
    assert combat._opening_initiator(WORLD, "", player) == ("enemy", "ambush")
    assert combat._opening_initiator(WORLD, "", None) == ("enemy", "ambush")
