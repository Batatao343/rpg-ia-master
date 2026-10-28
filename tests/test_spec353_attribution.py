"""SPEC-353 R11: os 3 textos reais do smoke passam por authorship(last_out) -> validate_attribution."""

from __future__ import annotations

import random

import pytest

from services import conflict_orchestrator as orch
from services import conflict_summary as summ
from services import round_log
from tests.fixtures import spec353_smoke as fx
from tests.test_fix_vitalidade_terminal import _actor, _scene


def _codes(text: str, last_out: dict) -> list[str]:
    auth = round_log.authorship(last_out, {"player": "Você", **fx.NAMES})
    return summ.validate_attribution(text, auth)


@pytest.mark.parametrize(
    ("text", "last_out", "code"),
    [
        (fx.D5, fx.LAST_OUT_D5, "V1"),
        (fx.K4, fx.LAST_OUT_K4, "V3"),
        (fx.R6, fx.LAST_OUT_R6, "V2"),
    ],
)
def test_real_smoke_texts_rejected_through_authorship(text, last_out, code):
    assert code in _codes(text, last_out)


def test_dot_final_blow_via_run_round_feeds_authorship():
    """Golpe final por DoT de aliado + heroi que errou, vindo do motor (nao escrito a mao)."""
    hero = _actor("player", corpo=5, is_player=True)
    boss = _actor("boss", corpo=0, categoria="lacaio", vitalidade=1)
    boss["active_conditions"] = [
        {"name": "Sangramento", "dot": 5, "duration": 3, "damage_type": "cortante"}
    ]
    out = orch.run_round(
        _scene("player", "boss"),
        {"player": hero, "boss": boss},
        {"hero": ["player"], "ally": [], "enemy": ["boss"]},
        declarations={},
        initiator="enemy",
        rng=random.Random(2),
    )
    auth = round_log.authorship(out, {"player": "Você", "boss": "Criatura"})
    assert auth["final_on_enemy"] and not auth["final_by_hero"]
    assert "V3" in summ.validate_attribution("Sua espada desce e a criatura desmorona.", auth)
    assert not summ.validate_attribution("O Sangramento derruba a criatura.", auth)
