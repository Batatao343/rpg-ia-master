"""SPEC-378 E2: ``env_choice`` e golden dos leitores de flag migrados.

O golden (``flag_readers.json``) foi gravado com os leitores ANTIGOS; regrave so com
``RPG_SPEC378_RECORD=1`` e justifique no commit.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from services.env import env_choice

GOLDEN = Path(__file__).parent / "fixtures" / "spec378" / "flag_readers.json"
VALUES = [None, "", "ON", " shadow ", "off", "on", "lixo", "\ton\n", "primary"]
DEPS = ("RPG_WORLD_ENGINE", "RPG_WORLD_QUESTS", "RPG_RUMORS", "RPG_RUMORS_PROPOSED")
READERS = [
    ("services.world_engine", "mode", "RPG_WORLD_ENGINE"),
    ("services.world_quests", "mode", "RPG_WORLD_QUESTS"),
    ("services.lore_quests", "mode", "RPG_LORE_QUESTS"),
    ("services.npc_world", "mode", "RPG_NPC_WORLD"),
    ("services.rumors", "mode", "RPG_RUMORS"),
    ("services.rumors", "proposed_mode", "RPG_RUMORS_PROPOSED"),
    ("services.rumor_adoption", "mode", "RPG_RUMORS_ADOPTED"),
    ("services.world_calendar", "mode", "RPG_CALENDAR"),
    ("services.npc_knowledge", "mode", "RPG_NPC_KNOWLEDGE"),
    ("services.law", "mode", "RPG_LAW"),
    ("services.opening_threads", "mode", "RPG_OPENING_THREAD"),
    ("services.scene_cards", "mode", "RPG_SCENE_CARDS"),
    ("services.shared_pool", "pool_mode", "RPG_SHARED_POOL"),
    ("services.jev_rollout", "rollout_mode", "RPG_JEV_ROUTER_MODE"),
    ("services.enemy_decks", "mode", "RPG_ENEMY_DECKS"),
    ("services.enemy_intent", "mode", "RPG_ENEMY_INTENT"),
    ("services.latency_flags", "two_phase_on", "RPG_NPC_TWO_PHASE"),
    ("services.latency_flags", "replan_after_on", "RPG_REPLAN_AFTER"),
    ("services.latency_flags", "day_digest_inline", "RPG_DAY_DIGEST"),
    ("services.latency_flags", "archive_policy", "RPG_ARCHIVE_POLICY"),
]


def _snapshot(monkeypatch) -> dict:
    out: dict[str, list] = {}
    for mod, fn, var in READERS:
        reader = getattr(importlib.import_module(mod), fn)
        rows = []
        for deps_on in (False, True):
            for value in VALUES:
                for d in DEPS:
                    monkeypatch.delenv(d, raising=False)
                    if deps_on:
                        monkeypatch.setenv(d, "on")
                if value is None:
                    monkeypatch.delenv(var, raising=False)
                else:
                    monkeypatch.setenv(var, value)
                rows.append([deps_on, value, reader()])
        monkeypatch.delenv(var, raising=False)
        out[f"{mod}.{fn}"] = rows
    return out


def test_flag_readers_match_golden(monkeypatch):
    got = _snapshot(monkeypatch)
    if os.environ.get("RPG_SPEC378_RECORD") == "1":
        GOLDEN.write_text(json.dumps(got, indent=1), encoding="utf-8")
    assert json.loads(json.dumps(got)) == json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw", [None, "", "ON", " shadow ", "off", "lixo", "\ton\n"])
def test_env_choice_semantics(monkeypatch, raw):
    if raw is None:
        monkeypatch.delenv("RPG_X_TEST", raising=False)
    else:
        monkeypatch.setenv("RPG_X_TEST", raw)
    choices = ("off", "shadow", "on")
    got = env_choice("RPG_X_TEST", choices, "off")
    legacy = os.getenv("RPG_X_TEST", "off").strip().lower()
    assert got == (legacy if legacy in choices else "off")
