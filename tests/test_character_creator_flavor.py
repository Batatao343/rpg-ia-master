"""Guard do flavor de criacao de personagem (SPEC-426 R4): AIMessage nao vira flavor."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

import character_creator as cc

_INPUT = {
    "name": "A",
    "class_name": "Devoto do Abismo",
    "race": "Humano",
    "region": "Nova Arcádia",
    "level": 1,
}


class _FakeLLM:
    def __init__(self, result: object) -> None:
        self._result = result

    def with_structured_output(self, *_a: object, **_k: object) -> _FakeLLM:
        return self

    def invoke(self, *_a: object, **_k: object) -> object:
        return self._result


def _names(sheet: dict) -> list[str]:
    return [str(e.get("display_name")) for e in sheet["inventory"]]


def test_flavor_from_structured_result_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    flavor = cc.PlayerFlavorSchema(inventory=["Adaga de Vidro-Dragão"], flavor_abilities=[])
    monkeypatch.setattr(cc, "get_llm", lambda *a, **k: _FakeLLM(flavor))
    sheet = cc.create_player_character(_INPUT, use_llm_flavor=True)
    assert "Adaga de Vidro-Dragão" in _names(sheet)


def test_aimessage_result_falls_back_without_flavor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cc, "get_llm", lambda *a, **k: _FakeLLM(AIMessage(content="erro")))
    sheet = cc.create_player_character(_INPUT, use_llm_flavor=True)
    assert "Adaga de Vidro-Dragão" not in _names(sheet)
    assert sheet["inventory"]  # inventario inicial da classe segue intacto
