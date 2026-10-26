"""SPEC-325 R1 - kill switches por capacidade de conflito."""

import pytest

from services import combat_flags as cf


def test_all_caps_have_distinct_env_vars():
    assert len(cf.CAPS) == 8
    assert len(set(cf.ENV_VARS.values())) == 8


@pytest.mark.parametrize("cap", cf.CAPS)
def test_default_is_shadow(cap, monkeypatch):
    monkeypatch.delenv(cf.ENV_VARS[cap], raising=False)
    assert cf.mode(cap) == "shadow"
    assert cf.shadow(cap) and not cf.active(cap)


@pytest.mark.parametrize("cap", cf.CAPS)
def test_invalid_falls_back_to_shadow(cap, monkeypatch):
    monkeypatch.setenv(cf.ENV_VARS[cap], "talvez")
    assert cf.mode(cap) == "shadow"


@pytest.mark.parametrize("value", ["off", "shadow", "on", " ON "])
def test_valid_values(value, monkeypatch):
    monkeypatch.setenv("RPG_COMBAT_NONLETHAL", value)
    assert cf.mode("nonlethal") == value.strip().lower()


def test_resistance_label_pt_br():
    assert cf.resistance_label("igneo:imune") == "Ígneo (imune)"
    assert cf.resistance_label("cortante:vulneravel") == "Cortante (vulnerável)"
    assert cf.resistance_label("legado") == "legado"
    assert cf.is_resistance_entry("igneo:imune")
    assert not cf.is_resistance_entry("igneo:talvez")
    assert not cf.is_resistance_entry("igneo")


def test_all_capability_flags_in_staging_allowlists():
    """Sem estar em `WORLD_FLAGS`/`OPTIONAL_FLAGS` o `vercel_env.py` apagaria a flag no staging."""
    from scripts.staging import vercel_env as ve

    for var in cf.ENV_VARS.values():
        assert var in ve.WORLD_FLAGS, var
        assert var in ve.OPTIONAL_FLAGS, var
