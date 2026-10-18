"""SPEC-180 rollout contract, kept after the SPEC-217 R14 port.

The policy/router behaviour is covered by ``tests/test_jev_router_port.py``;
this file keeps the reversible-mode and idempotency guarantees.
"""

from __future__ import annotations

import pytest

from services import jev_rollout


def state():
    return {"game_id": "game-1", "world": {"turn_count": 3, "current_location": "Vila"},
            "combat": {"active": False}}


def test_off_and_invalid_config_never_start(monkeypatch: pytest.MonkeyPatch) -> None:
    started = []
    monkeypatch.setattr(jev_rollout, "_pool", lambda: started.append(1))
    for mode in ("off", "typo", ""):
        monkeypatch.setenv("RPG_JEV_ROUTER_MODE", mode)
        assert jev_rollout.rollout_mode() == "off"
        assert jev_rollout.begin(state(), "Olho o altar") is None
    monkeypatch.delenv("RPG_JEV_ROUTER_MODE")
    assert jev_rollout.begin(state(), "Olho o altar") is None
    assert not started


def test_modes_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    for mode in ("shadow", "PRIMARY", " off "):
        monkeypatch.setenv("RPG_JEV_ROUTER_MODE", mode)
        assert jev_rollout.rollout_mode() == mode.strip().lower()


def test_idempotency_key_is_stable_and_textless() -> None:
    key = jev_rollout._idempotency_key(state(), "Olho o altar")
    assert key == jev_rollout._idempotency_key(state(), "Olho o altar")
    assert key != jev_rollout._idempotency_key(state(), "Olho a porta")
    assert key.startswith("rpg-router-") and "altar" not in key.lower()


def test_threshold_requires_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    assert jev_rollout._threshold() == 0.50
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", ("", 0.5))
    assert jev_rollout._threshold() is None
    monkeypatch.setattr(jev_rollout, "PRIMARY_CALIBRATION", ("x", 1.5))
    assert jev_rollout._threshold() is None
