"""SPEC-363 R22/R24: o veredito da fuga vem da perseguição e fala a mesma coisa em todo lugar."""

from __future__ import annotations

import pytest

import agents.combat as combat
from services import chase
from services import combat_preview as cp


@pytest.mark.parametrize(
    "state,prev,fled,expected",
    [
        (
            {"escapou": True, "_last": {"sucesso": True, "total": 20}},
            "quase_livre",
            True,
            "escapou",
        ),
        (
            {"alcancado": True, "_last": {"sucesso": False, "total": 3}},
            "pressionado",
            False,
            "alcancado",
        ),
        (
            {"trilha": "afastado", "_last": {"sucesso": True, "total": 16}},
            "pressionado",
            False,
            "avancou",
        ),
        (
            {"trilha": "pressionado", "_last": {"sucesso": False, "total": 4}},
            "afastado",
            False,
            "perdeu_terreno",
        ),
    ],
)
def test_flee_verdict_matches_chase(state, prev, fled, expected):
    assert combat._flee_verdict(state, prev, fled) == expected


def test_mech_log_flee_line_uses_verdict_not_roll():
    roll = {
        "total": 16,
        "dificuldade": 12,
        "sucesso": True,
        "veredito": "avancou",
        "de": "pressionado",
        "para": "afastado",
    }
    line = cp._flee_line({"fuga": roll})
    assert line == "Fuga · total 16 vs 12 · avança (pressionado → afastado)"
    assert "escapou" not in line
    lost = cp._flee_line(
        {
            "fuga": {
                **roll,
                "sucesso": False,
                "veredito": "perdeu_terreno",
                "de": "afastado",
                "para": "pressionado",
            }
        }
    )
    assert lost.endswith("perde terreno (afastado → pressionado)")
    assert cp._flee_line({"fuga": {**roll, "veredito": "escapou"}}).endswith("escapou")
    # save antigo, sem veredito: não afirma "escapou" só porque o dado passou
    assert "escapou" not in cp._flee_line(
        {"fuga": {"total": 9, "dificuldade": 12, "sucesso": True}}
    )


def test_flee_lines_use_labels_and_voce():
    assert chase.track_label("quase_livre") == "quase livre"
    assert chase.track_label("escapou") == "livre"
    state = {"trilha": "afastado", "_last": {"sucesso": True}}
    text = f"Você avança na fuga: {chase.track_label('pressionado')} → {chase.track_label(state['trilha'])}."
    assert "_" not in text and "Você" in text


def test_status_logs_are_normalized_once():
    player = {"name": "Mirela"}
    lines = combat._normalize_status_logs(
        [
            "Mirela: ganha condição cego",
            "Mirela: ganha condição cego",
            "Mirela: condição Cego renovada",
        ],
        player,
    )
    assert lines == ["Você ganha a condição Cego.", "Sua condição Cego foi renovada."]
