"""SPEC-317 R9 — ordem estático-primeiro nos prompts de narrador, NPC e router."""

from __future__ import annotations

import pytest

from services import prompt_layout
from tests.prompt_capture import capture

_DYNAMIC_MARKER = {"story": "<PERSONA>", "npc": "<ROLE>", "router": "Local Atual:"}
_STATIC_MARKER = {"story": "<INSTRUÇÕES>", "npc": "<REGRAS DE ATUAÇÃO", "router": "REGRAS:"}


# sha256 dos prompts gerados pelo codigo de `main` ANTES da SPEC-317 (flag off), na fixture de
# tests/prompt_capture.py. Mudanca legitima de prompt em outra spec atualiza estes hashes.
_MAIN_GOLDEN = {
    "npc": "b6bd8f60d58defd157f24595e7f48528b27f47590d2fb05ac4212cd94953bc45",
    "router": "adbe6157f91b7a7ba50ff33a620fea95b79246861ca639924cdfd3abadd3fd46",
    "story": "34ddf51f41975b7bf4b39b9ba39ff4f0c0f2ceb4452b43db760cab7cec20e696",
}


def _lines(text: str) -> list[str]:
    return sorted(
        line.strip()
        for line in text.splitlines()
        if line.strip() and line.strip() != prompt_layout.DYNAMIC_LABEL
    )


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
    import hashlib

    for key, golden in _MAIN_GOLDEN.items():
        assert hashlib.sha256(first[key].encode("utf-8")).hexdigest() == golden, key
    parts = [("a\n", True), ("b\n", False), ("c\n", True)]
    assert prompt_layout.compose(parts, static_first=False) == "a\nb\nc\n"
    assert prompt_layout.compose(parts, static_first=True).index("c") < prompt_layout.compose(
        parts, static_first=True
    ).index("b")
