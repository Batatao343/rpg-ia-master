"""SPEC-378 E6: ``is_database_profile`` == expressao antiga, inclusive ``""`` -> True."""

from __future__ import annotations

import os

import pytest

from services.env import is_database_profile

CASES = [None, "", "legacy", " LEGACY ", "local", "hosted-supabase", "lixo"]


@pytest.mark.parametrize("raw", CASES)
def test_matches_legacy_expression(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("RPG_RUNTIME_PROFILE", raising=False)
    else:
        monkeypatch.setenv("RPG_RUNTIME_PROFILE", raw)
    old = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy"
    assert is_database_profile() is old
    if raw == "":
        assert is_database_profile() is True
