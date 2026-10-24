"""SPEC-303 R28 (rapido): S2 e S3 sempre valem em 60 dias x 3 seeds."""

from __future__ import annotations

import importlib.util
import pathlib

import pytest


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_CALENDAR", "on")


def _sim():
    path = pathlib.Path("docs/spec302/world_engine_sim.py")
    spec = importlib.util.spec_from_file_location("world_engine_sim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_s2_s3_hold_short_run():
    out = _sim().evaluate_s303(seeds=3, days=60)
    assert out["S2_extra_crises_from_season"] == []
    assert out["S3_ok"] is True
    assert out["S4_ok"] is True
