"""SPEC-371 R17/R18/R21: flag `off` byte-idêntica, flag registrada e playtest com a flag `on`."""

from __future__ import annotations

import json

import pytest

from tests.test_spec360_flags_off import GOLDEN, _fingerprint, _flags, _run


def test_flag_registrada_off_por_padrao():
    from pathlib import Path

    import yaml

    reg = yaml.safe_load((Path(__file__).parents[1] / "config" / "flags.yaml").read_text("utf-8"))
    flags = reg.get("flags", reg)
    row = flags["RPG_FAUNA_SABER"]
    assert row["default"] == "off" and row["kind"] == "release" and row["spec"] == "SPEC-371"
    assert str(row["expires"]) == "2027-03-01"


def test_modo_invalido_vale_off(monkeypatch):
    from services import fauna_saber

    monkeypatch.setenv("RPG_FAUNA_SABER", "talvez")
    assert fauna_saber.mode() == "off"
    monkeypatch.delenv("RPG_FAUNA_SABER")
    assert fauna_saber.mode() == "off"


def test_golden_360_inalterado_com_a_flag_off(monkeypatch):
    """R18: 30 turnos do `explorador` com a flag explicitamente `off` igualam o golden da 360."""
    _flags(monkeypatch, "off", "off")
    monkeypatch.setenv("RPG_FAUNA_SABER", "off")
    assert _fingerprint(_run()) == json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("profile", ["combate"])
def test_playtest_combate_com_saber_on_sem_violacao(monkeypatch, profile):
    """R21: campanha de combate com a flag `on` (decks e intencao `on`): 0 violacao `error`."""
    from playtest.runner import run_campaign

    monkeypatch.setenv("RPG_FAUNA_SABER", "on")
    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    result = run_campaign(profile, turns=30, seed=0)
    assert not result.errors
    erros = [v for v in result.violations if v.get("severity") == "error"]
    assert not erros, erros[:3]


def test_invariante_saber_valido_pega_dado_ruim():
    from playtest.invariants import check_saber

    ruim = {
        "bestiary_knowledge": {
            "mon_arame_vivo": {
                "sinais_vistos": ["tipo_inexistente"],
                "assinaturas_sobrevividas": -1,
                "telegrafos_vistos": list("abcde"),
                "saber_revelado": {"motivo": "chute", "turn": 1},
            },
            "enemy_rato_peste_anel_lama": {"saber_revelado": {"motivo": "estudada", "turn": 1}},
        }
    }
    msgs = {v.message for v in check_saber(ruim, None, 3)}
    assert {
        "sinal_vistos fora dos tipos",
        "assinaturas_sobrevividas invalido",
        "telegrafos_vistos acima do cap",
        "motivo de revelacao invalido",
        "revelado sem contra-jogo",
    } <= msgs
    bom = {
        "bestiary_knowledge": {
            "mon_arame_vivo": {
                "sinais_vistos": ["rastro"],
                "assinaturas_sobrevividas": 1,
                "telegrafos_vistos": ["a"],
                "saber_revelado": {"motivo": "sobreviveu", "turn": 2},
            }
        }
    }
    assert check_saber(bom, None, 3) == []
