"""SPEC-367 R13/R14: condição de inimigo que termina lê como frase, uma vez, em todas as superfícies."""

from __future__ import annotations

import re

from agents import combat
from services import round_log

RAW = re.compile(r"^[^:]+: \w+ terminou")
ACTORS = {
    "player": {"id": "player", "name": "Mirela5", "is_player": True},
    "g1": {"id": "g1", "name": "Goblin-Mineiro"},
}


def test_enemy_condition_end_readable():
    assert (
        round_log._voce("Goblin-Mineiro: cego terminou.", "Mirela5")
        == "A condição Cego de Goblin-Mineiro terminou."
    )
    assert (
        round_log._voce("Goblin-Mineiro: Provocação terminou.", "Mirela5")
        == "A condição Provocação de Goblin-Mineiro terminou."
    )


def test_hero_condition_end_unchanged():
    assert round_log._voce("Mirela5: Cego terminou.", "Mirela5") == "Sua condição Cego terminou."


def test_condition_end_once_on_all_surfaces():
    raw = "Goblin-Mineiro: cego terminou."
    out = {"logs": [raw], "attacks": []}
    lines = round_log.round_registry(out, ACTORS, status_logs=[raw])
    hits = [x for x in lines if "terminou" in x]
    assert hits == ["A condição Cego de Goblin-Mineiro terminou."]
    status = combat._normalize_status_logs([raw, raw], ACTORS["player"])
    assert status == ["A condição Cego de Goblin-Mineiro terminou."]
    for line in [*lines, *status]:
        assert ": cego terminou" not in line and not RAW.match(line)
