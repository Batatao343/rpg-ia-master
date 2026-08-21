from __future__ import annotations

import pytest

from gamedata import prepared_slots_for_level
from playtest.runner import _build_initial_state
from playtest.matrix import LONGRUN_MATRIX, case_label, select_matrix_cases
from services.cards import get_card


@pytest.mark.parametrize("level", [1, 3, 9, 20])
def test_estado_inicial_respeita_nivel_e_resolve_escolhas(level):
    state = _build_initial_state(
        "normal", seed=6200 + level, class_name="Devoto do Abismo",
        start_level=level,
    )
    player = state["player"]
    assert player["level"] == level
    assert player["gold"] == 50 * level
    assert not player.get("pending_choices")
    assert len(player.get("prepared_cards") or []) <= prepared_slots_for_level(level)
    assert state["world"]["danger_level"] >= 1
    if level >= 3:
        assert player.get("subclass")
    if level >= 9:
        assert any(
            int((get_card(card_id) or {}).get("level_req", 1) or 1) >= 9
            for card_id in player.get("prepared_cards") or []
        )
    if level == 20:
        assert any("apex" in grant for grant in player.get("progression_grants", []))


def test_estado_inicial_rejeita_nivel_fora_do_jogo():
    with pytest.raises(ValueError, match="entre 1 e 20"):
        _build_initial_state("normal", seed=1, start_level=21)


def test_matriz_tem_dez_casos_pareaveis_e_cobre_niveis_extremos():
    assert len(LONGRUN_MATRIX) == 10
    assert len({case_label(case) for case in LONGRUN_MATRIX}) == 10
    assert [case["seed"] for case in LONGRUN_MATRIX] == list(range(6200, 6210))
    assert {case["start_level"] for case in LONGRUN_MATRIX} >= {1, 9, 20}
    assert len({case["class_name"] for case in LONGRUN_MATRIX}) == 5


def test_continuacao_da_matriz_preserva_cauda_canonica():
    selected = select_matrix_cases(5)

    assert [case["index"] for case in selected] == list(range(5, 11))
    assert selected[0] == {
        "index": 5, "profile": "comerciante", "class_name": "Corruptor",
        "start_level": 9, "seed": 6204,
    }
    assert select_matrix_cases() == LONGRUN_MATRIX
