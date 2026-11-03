"""SPEC-370 R15: com ~400 entradas em `fauna.json` a ecologia segue barata."""

from __future__ import annotations

import time

import pytest

from services import fauna

N = 400
TETO_MS = 20.0


@pytest.fixture
def grande(monkeypatch):
    base = fauna.entry("mon_porca_da_queda")
    crit = {}
    for i in range(N):
        cid = f"sint_{i:03d}"
        crit[cid] = {**base, "id": cid, "regiao": "nova_arcadia", "predadores": []}
    monkeypatch.setattr(fauna, "load", lambda: crit)
    return crit


def _ms(fn, reps: int = 50) -> float:
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t0) * 1000 / reps


def test_eco_multiplier_barato(grande):
    ctx = fauna.EcoCtx(
        location_id="na_anel_lama", region_id="nova_arcadia", period="Noite", season=None
    )
    e = grande["sint_000"]
    assert _ms(lambda: fauna.eco_multiplier(e, ctx)) < TETO_MS


def test_scene_block_barato(grande, monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    state = {
        "world": {"current_location_id": "na_anel_lama", "world_clock": {"day": 3}},
        "world_sim": {},
    }
    assert _ms(lambda: fauna.scene_block(state)) < TETO_MS


def test_loader_carrega_uma_vez():
    fauna.load.cache_clear()
    fauna.load()
    assert fauna.load.cache_info().misses == 1
    fauna.load()
    assert fauna.load.cache_info().hits >= 1
