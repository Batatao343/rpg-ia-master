"""SPEC-364 R14-R16: Cartas de Cena na voz do jogador; uma linha por evento de condicao."""

from __future__ import annotations

import pytest

from services import round_log

ACTORS = lambda hero: {  # noqa: E731
    "player": {"name": hero, "is_player": True},
    "enemy_gob": {"name": "Goblin"},
}


@pytest.mark.parametrize("hero", ["Smoke4A", "Mirela4"])
def test_scene_charge_line_uses_voce(hero):
    out = {"scene_logs": [f"{hero} sente o Abismo mais perto (+1 Carga)."]}
    lines = round_log.round_registry(out, ACTORS(hero))
    assert lines == ["Você sente o Abismo mais perto (+1 Carga)."]


@pytest.mark.parametrize("hero", ["Smoke4A", "Mirela4"])
def test_scene_condition_hero_line(hero):
    out = {"scene_logs": [f"{hero}: ganha condição cego"]}
    assert round_log.round_registry(out, ACTORS(hero)) == ["Você ganha a condição Cego."]


def test_scene_condition_line_once():
    out = {
        "logs": ["Goblin ganha a condição Cego."],
        "scene_logs": ["Goblin: ganha condição cego"],
    }
    lines = round_log.round_registry(out, ACTORS("Smoke4A"))
    assert sum("Cego" in ln for ln in lines) == 1


@pytest.mark.parametrize("hero", ["Smoke4A", "Mirela4"])
def test_no_hero_name_in_player_surfaces(hero):
    out = {
        "logs": [f"{hero}: ganha condição cego"],
        "scene_logs": [
            f"{hero} sente o Abismo mais perto (+1 Carga).",
            f"{hero}: ganha condição cego",
        ],
    }
    lines = round_log.round_registry(
        out, ACTORS(hero), status_logs=[f"{hero}: ganha condição cego"]
    )
    for ln in lines:
        assert not ln.startswith(hero) and f"{hero}:" not in ln, ln
    assert sum("Cego" in ln for ln in lines) == 1
