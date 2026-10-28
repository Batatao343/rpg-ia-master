"""SPEC-345 R4/R5: texto ao jogador sem rótulos, ids nem tags internas."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from services import conflict_summary as cs
from services.presentation_history import history_page
from services.turn_outcome import (
    EMPTY_NARRATION_TEXT,
    player_facing_message,
    strip_system_tags,
)


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ({"mortos": ["Bandido"]}, "Bandido tomba."),
        (
            {"mortos": ["Bandido 1", "Bandido 2"], "fugitivos": ["Lobo"]},
            "Bandido 1 e Bandido 2 tombam. Lobo foge.",
        ),
        ({"mortos": ["A", "B", "C"]}, "A, B e C tombam."),
        ({"caidos": ["X"]}, "X cai."),
        ({"rendidos": ["X", "Y"]}, "X e Y se rendem."),
        ({"capturados": ["X"]}, "X é capturado."),
        ({"inconscientes": ["X"]}, "X perde os sentidos."),
        ({}, EMPTY_NARRATION_TEXT),
        (
            {"loot_obtido": [{"kind": "item", "item_id": "adaga_ferro", "qty": 1}]},
            EMPTY_NARRATION_TEXT,
        ),
    ],
)
def test_player_summary_templates(summary, expected):
    text = cs.player_summary_text(summary)
    assert text == expected
    assert "_" not in text and "Mortos:" not in text and "Espólio" not in text


def test_canonical_summary_text_inalterado():
    assert cs.canonical_summary_text({"mortos": ["B"]}) == "Mortos: B."


def test_contradicao_usa_resumo_jogador():
    summary = {"mortos": ["Bandido"]}
    out = cs.narrative_or_fallback(summary, "Bandido sobrevive ao golpe.", player_facing=True)
    assert out == "Bandido tomba."


def test_sistema_prefixo_removido_conteudo_mantido():
    text = "O baú range.\n[SISTEMA] Adaga de Ferro (incomum) e +12 de ouro"
    out = strip_system_tags(text)
    assert "[SISTEMA]" not in out
    assert out.endswith("Adaga de Ferro (incomum) e +12 de ouro")


def test_resultado_linha_inteira_removida():
    assert strip_system_tags("Prosa.\n[RESULTADO] Voce ganhou 5 ouro\nFim.") == "Prosa.\nFim."


def test_idempotente():
    once = strip_system_tags("a\n\n\n[SISTEMA] b\n[RESULTADO] c")
    assert strip_system_tags(once) == once


def test_316_f1_so_recibo_post():
    state = {"messages": [AIMessage(content="[RESULTADO] Voce ganhou 500 ouro")]}
    assert player_facing_message(state) == EMPTY_NARRATION_TEXT


def test_316_f1_so_recibo_sse():
    from services.turn_delivery import early_narrative
    from tests.test_turn_delivery import _state

    text = early_narrative(
        _state(),
        {"messages": [AIMessage(content="[RESULTADO] Voce ganhou 500 ouro")]},
        "storyteller",
    )
    assert text is not None
    assert "[RESULTADO]" not in text and "500" not in text


def test_history_limpa_entrada_antiga():
    state = {
        "presentation_history": [
            {
                "id": "1",
                "turn": 1,
                "epoch": 0,
                "role": "narrator",
                "type": "STORY",
                "text": "Achou.\n[SISTEMA] +5 de ouro",
                "speaker_kind": "narrator",
            },
        ],
        "messages": [HumanMessage("x")],
    }
    page = history_page(state)
    assert page["entries"][0]["text"] == "Achou.\n+5 de ouro"
    assert "[SISTEMA]" in state["presentation_history"][0]["text"]


def test_mensagem_interna_mantem_ledger(monkeypatch):
    from agents import loot
    from tests.test_review_high_integration import (
        _conflict_summary,
        _HallucinatingLootLLM,
        _player,
    )

    monkeypatch.setattr(loot, "get_llm", lambda **_k: _HallucinatingLootLLM())
    monkeypatch.setattr(
        loot, "get_location", lambda _i: {"id": "ponte", "name": "Ponte", "region_id": "planicie"}
    )
    monkeypatch.setattr(
        loot.economy,
        "roll_loot",
        lambda *_a, **_k: {"gold": 7, "item_id": None, "rarity": "common"},
    )
    out = loot.loot_node(
        {
            "player": _player(),
            "world": {"current_location_id": "ponte", "danger_level": 1, "turn_count": 3},
            "combat": {"encounter_level": 4},
            "conflict_summary": _conflict_summary(),
            "loot_source": "TREASURE",
            "messages": [HumanMessage(content="Vasculho os corpos.")],
            "world_projection": {},
            "bestiary_knowledge": {},
        }
    )
    internal = out["messages"][0].content
    assert "[SISTEMA] +7 de ouro" in internal  # R5.5
    assert (
        "Brutamontes tomba." in internal
        and "Mortos:" not in internal
        and "Espólio:" not in internal
    )
    shown = player_facing_message({"messages": out["messages"]})
    assert "[SISTEMA]" not in shown and "+7 de ouro" in shown
