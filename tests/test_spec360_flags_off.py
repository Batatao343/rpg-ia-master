"""SPEC-360 R25-R27: flags `off` byte-identicas, zero chamada LLM nova e latencia.

O golden (`tests/fixtures/spec360_flags_off_golden.json`) foi gravado na Etapa 0, ANTES de
qualquer codigo de produto da SPEC-360 (`SPEC360_REGEN=1` regrava; so o coordenador).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

GOLDEN = Path(__file__).parent / "fixtures" / "spec360_flags_off_golden.json"
TURNS = 30


def _sha(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def _fingerprint(result) -> dict:
    turns = [
        [
            r.action,
            r.route,
            r.location_id,
            int(r.player_vitality),
            int(r.gold),
            int(r.player_level),
            bool(r.combat_started),
            bool(r.combat_ended),
            len(r.llm_events),
        ]
        for r in result.history
    ]
    st = result.final_state or {}
    msgs = [str(getattr(m, "content", m)) for m in st.get("messages") or []]
    world = dict(st.get("world") or {})
    return {
        "turns": turns,
        "messages": _sha(msgs),
        "world_clock": world.get("world_clock"),
        "location": world.get("current_location_id"),
        "bestiary_knowledge": _sha(st.get("bestiary_knowledge") or {}),
        "errors": len(result.errors),
    }


def _run(profile: str = "explorador", turns: int = TURNS):
    from playtest.runner import run_campaign

    return run_campaign(profile, turns=turns, seed=0, invariants=False)


def _flags(monkeypatch, fauna: str, sinais: str) -> None:
    monkeypatch.setenv("RPG_FAUNA", fauna)
    monkeypatch.setenv("RPG_FAUNA_SINAIS", sinais)


def test_golden_flags_off_byte_identico(monkeypatch):
    """R25: com as duas flags `off`, 30 turnos do `explorador` igualam o golden da Etapa 0."""
    _flags(monkeypatch, "off", "off")
    fp = _fingerprint(_run())
    if os.getenv("SPEC360_REGEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(fp, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        pytest.skip("golden regravado")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert fp == golden
