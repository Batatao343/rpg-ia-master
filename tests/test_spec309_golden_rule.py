"""SPEC-309 Etapa 2 + §3.6: oraculo estrutural da regra de ouro (pack, bloco, memoria)."""

from __future__ import annotations

import re

import pytest

from agents.archivist import _event_memory_records
from services.context_builder import build_context_pack
from services.perceived_world import perceived_world_block
from tests.spec309_helpers import FACT_B, world_state_two_regions

_AUDIENCES = ("story", "npc", "combat", "day")
_FORBIDDEN = re.compile(r"severidade|pressão|tensão|fase|banda|multa|recompensa", re.I)


def _all_texts(state):
    pack = build_context_pack(state, "o que acontece", "story").world_state_block
    blocks = [perceived_world_block(state, audience=a) for a in _AUDIENCES]
    mem = [r["text"] for r in _event_memory_records(state["event_log"], state)]
    return pack, blocks, mem


def test_unperceived_siege_and_fate_never_leak():
    """§3.6 itens 1 e 3."""
    pack, blocks, mem = _all_texts(world_state_two_regions())
    haystack = "\n".join([pack, *blocks, *mem])
    assert "sitiada" not in haystack and "Brekmar agora" not in haystack  # grafo base cita Brekmar
    assert "Zedrik" not in haystack


def test_perceived_warning_in_pack_and_block():
    """§3.6 item 2."""
    pack, blocks, _mem = _all_texts(world_state_two_regions())
    assert FACT_B in pack
    assert FACT_B in blocks[0]


def test_no_digits_or_forbidden_words_in_blocks():
    """§3.6 item 4."""
    _pack, blocks, _mem = _all_texts(world_state_two_regions(season="inverno"))
    for b in blocks:
        assert not _FORBIDDEN.search(b)
        assert not re.search(r"\d", b)


def test_siege_perceived_appears_in_pack_not_in_block():
    """§3.6 item 5: Brekmar e de OUTRA regiao => pack sim, bloco nao."""
    state = world_state_two_regions(perceive_siege=True)
    pack, blocks, _mem = _all_texts(state)
    assert "Brekmar agora está sitiada" in pack
    assert all("Brekmar" not in b for b in blocks)


def test_engine_types_not_in_event_memory():
    """R9: tipos do motor so viram memoria pelo digest percebido."""
    state = world_state_two_regions(perceive_siege=True)
    types = {e["type"] for e in state["event_log"]}
    assert {"location_state_changed", "world_crisis_warning"} <= types
    assert _event_memory_records(state["event_log"], state) == []


def test_witnessed_types_in_event_memory():
    state = world_state_two_regions()
    ev = {
        "event_id": "e-left",
        "type": "companion_left",
        "turn": 9,
        "actor_id": "comp",
        "target_id": "comp",
        "payload": {"name": "Mira"},
        "source": "engine",
    }
    texts = [r["text"] for r in _event_memory_records([ev], state)]
    assert texts == ["[turno 9] Mira deixou o grupo."]


@pytest.mark.parametrize("perceived", [False, True])
def test_companion_fate_needs_perception(perceived):
    state = world_state_two_regions()
    fate = next(e for e in state["event_log"] if e["type"] == "companion_fate")
    if perceived:
        state["world_sim"]["perceived_ids"].append(fate["event_id"])
    texts = [r["text"] for r in _event_memory_records([fate], state)]
    assert bool(texts) is perceived
