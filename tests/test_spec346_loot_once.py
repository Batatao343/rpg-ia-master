"""SPEC-346 R19-R22: o espólio do encontro é reclamado uma vez só; voz do protagonista com caixa certa."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.loot as loot
from services import encounter_manifest as em
from services import prose_guard

LOC = "pantano_melancolia"


def _manifest(label="Criatura do Poço"):
    enemy = {"id": "poco_1", "name": label, "species_label": label, "status": "ativo"}
    return em.build_manifest(
        [enemy], source="scanner", origin="player_provoked", encounter_id="g:0:4", scene={}
    )


def _state(text, *, combat=None, gold=10):
    return {
        "game_id": "g",
        "player": {"name": "Torvin", "gold": gold, "inventory": [], "level": 3},
        "world": {"current_location_id": LOC, "current_location": "Pântano", "turn_count": 5},
        "messages": [AIMessage(content="A criatura tomba."), HumanMessage(content=text)],
        "loot_source": "TREASURE",
        "combat": combat or {},
        "conflict_summary": {},
    }


CLAIMED = {
    "phase": "ended",
    "encounter": None,
    "result": {
        "encounter_id": "g:0:4",
        "outcome": "victory",
        "loot_claimed": True,
        "loot_turn": 4,
        "location_id": LOC,
    },
}


def _spy_events(monkeypatch):
    events = []
    monkeypatch.setattr(loot, "_log_event", lambda *a, **k: events.append(a[:2]))
    return events


def test_corpse_search_after_claimed_loot_does_not_reroll(monkeypatch):
    events = _spy_events(monkeypatch)
    state = _state("Vasculho o corpo da criatura", combat=CLAIMED)
    out = loot.loot_node(state)
    assert out["messages"][0].content == loot.CORPSE_ALREADY_LOOTED
    assert "player" not in out  # ouro e inventário inalterados
    assert ("loot", "corpse_already_looted") in events


def test_corpse_search_by_species_label_also_blocked(monkeypatch):
    combat = {**CLAIMED, "encounter": _manifest()}
    out = loot.loot_node(_state("Reviro a criatura do poço de novo", combat=combat))
    assert out["messages"][0].content == loot.CORPSE_ALREADY_LOOTED


def test_environment_search_still_rolls(monkeypatch):
    monkeypatch.setattr(loot, "_narrate", lambda *a, **k: "Você vasculha a sala.")
    random.seed(2)
    out = loot.loot_node(_state("Vasculho a sala em busca de algo", combat=CLAIMED))
    assert "[SISTEMA]" in out["messages"][0].content
    assert out["player"]["gold"] >= 10


def test_other_location_does_not_block(monkeypatch):
    monkeypatch.setattr(loot, "_narrate", lambda *a, **k: "ok")
    state = _state("Vasculho o corpo", combat=CLAIMED)
    state["world"]["current_location_id"] = "skallgard"
    out = loot.loot_node(state)
    assert "[SISTEMA]" in out["messages"][0].content


def test_old_save_without_loot_claimed_allows_search(monkeypatch):
    monkeypatch.setattr(loot, "_narrate", lambda *a, **k: "ok")
    old = {"phase": "ended", "result": {"encounter_id": "g:0:4", "outcome": "victory"}}
    out = loot.loot_node(_state("Vasculho o corpo", combat=old))
    assert "[SISTEMA]" in out["messages"][0].content


def test_corpse_context_mentions_species(monkeypatch):
    seen = {}

    def fake(context, fallback, summary=None):
        seen["context"] = context
        return "ok"

    monkeypatch.setattr(loot, "_narrate", fake)
    combat = {"phase": "active", "encounter": _manifest()}
    loot.loot_node(_state("Vasculho o corpo", combat=combat))
    assert "o corpo de Criatura do Poço" in seen["context"]
    assert "O jogador" not in seen["context"] and "Você vasculha" in seen["context"]


def test_environment_context_has_location_and_you(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        loot, "_narrate", lambda context, fb, summary=None: seen.setdefault("c", context) or "ok"
    )
    loot.loot_node(_state("Vasculho a sala"))
    assert "Você vasculha" in seen["c"] and "O jogador" not in seen["c"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Em Skallgard, o jogador arranca a pedra.", "Em Skallgard, você arranca a pedra."),
        ("O jogador avança.", "Você avança."),
        ("Ele cai. O jogador respira.", "Ele cai. Você respira."),
        ("Quando o herói sai\nO personagem olha.", "Quando você sai\nVocê olha."),
    ],
)
def test_protagonist_voice_case(raw, expected):
    assert prose_guard.normalize_protagonist_voice(raw) == expected


def test_residual_conflict_summary_next_turn_does_not_reroll(monkeypatch):
    """P2-3: arquivista não limpou o resumo; 'revisto o corpo' no turno seguinte não rerrola."""
    state = _state("Revisto o corpo", combat=CLAIMED)
    state["conflict_summary"] = {"mortos": ["Criatura do Poço"]}
    out = loot.loot_node(state)
    assert out["messages"][0].content == loot.CORPSE_ALREADY_LOOTED
    assert "player" not in out
