"""SPEC-317 R9 — ordem estático-primeiro nos prompts de narrador, NPC e router."""

from __future__ import annotations

import pytest

from services import prompt_layout
from tests.prompt_capture import capture

_DYNAMIC_MARKER = {"story": "<PERSONA>", "npc": "<ROLE>", "router": "Local Atual:"}
_STATIC_MARKER = {"story": "<INSTRUÇÕES>", "npc": "<REGRAS DE ATUAÇÃO", "router": "REGRAS:"}


def _lines(text: str) -> list[str]:
    return sorted(line.strip() for line in text.splitlines() if line.strip())


@pytest.fixture()
def prompts(monkeypatch):
    monkeypatch.delenv("RPG_PROMPT_STATIC_FIRST", raising=False)
    off = capture(monkeypatch)
    monkeypatch.setenv("RPG_PROMPT_STATIC_FIRST", "on")
    on = capture(monkeypatch)
    return off, on


def test_static_first_keeps_same_token_set(prompts):
    off, on = prompts
    assert set(off) == set(on) == {"story", "npc", "router"}
    for key in off:
        assert _lines(off[key]) == _lines(on[key]), key


def test_dynamic_header_is_last_when_flag_on(prompts):
    off, on = prompts
    for key in off:
        d, s = _DYNAMIC_MARKER[key], _STATIC_MARKER[key]
        assert off[key].index(d) < off[key].index(s), key  # ordem original
        assert on[key].index(s) < on[key].index(d), key  # estático primeiro


def test_flag_off_byte_identical(monkeypatch):
    monkeypatch.delenv("RPG_PROMPT_STATIC_FIRST", raising=False)
    first = capture(monkeypatch)
    monkeypatch.setenv("RPG_PROMPT_STATIC_FIRST", "off")
    second = capture(monkeypatch)
    assert first == second
    parts = [("a\n", True), ("b\n", False), ("c\n", True)]
    assert prompt_layout.compose(parts, static_first=False) == "a\nb\nc\n"
    assert prompt_layout.compose(parts, static_first=True).index("c") < prompt_layout.compose(
        parts, static_first=True
    ).index("b")
