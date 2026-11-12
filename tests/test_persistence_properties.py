"""SPEC-417 R13: round-trip save/load por propriedade (RT1 preserva, RT2 ponto fixo, RT3 pura).

Estado = `make_state` (classe/raça/região de listas pequenas do catálogo, para o cache de
`_sheet`) mutado em ouro, vitalidade, inventário, turno, ids processados, `archivist_last_run`,
`conflict_summary` e mensagens. O `conftest.py` já isola `saves/`. Normalizações aceitas de
save/load, e só elas: `processed_action_ids` = últimos 64; `player.vitalidade_base_bonus`;
`world.shelter = None`; `conflict_summary` ganha `conflict_id`/`conflict_turn`.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from langchain_core.messages import AIMessage, HumanMessage

import persistence
from gamedata import ARTIFACTS_DB
from tests.factories import make_state
from tests.fakes.property_settings import deterministic_settings

PLAYER_EXTRA = {"vitalidade_base_bonus"}
WORLD_EXTRA = {"shelter"}
TEXT = st.text(st.characters(blacklist_categories=("Cs",)), max_size=40)
MESSAGES = st.lists(
    st.builds(
        lambda cls, text: cls(content=text), st.sampled_from([HumanMessage, AIMessage]), TEXT
    ),
    max_size=4,
)
CONFLICT = st.none() | st.fixed_dictionaries(
    {"rounds": st.integers(0, 9)}, optional={"summary": TEXT}
)


@st.composite
def states(draw: st.DrawFn) -> dict[str, Any]:
    n = draw(st.integers(0, 10**6))
    state = copy.deepcopy(
        make_state(
            game_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"prop/{n}")),
            class_name=draw(st.sampled_from(["Guerreiro", "Mago"])),
            level=draw(st.integers(1, 3)),
        )
    )
    player = state["player"]
    player["gold"] = draw(st.integers(0, 5000))
    player["vitalidade"] = draw(st.integers(0, int(player["max_vitalidade"])))
    ids = draw(st.lists(st.sampled_from(sorted(ARTIFACTS_DB)), max_size=5, unique=True))
    player["inventory"] = [{"id": i, "qty": draw(st.integers(1, 99))} for i in ids]
    state["world"]["turn_count"] = draw(st.integers(0, 10_000))
    big = st.lists(st.text(min_size=1, max_size=8), min_size=65, max_size=100, unique=True)
    state["processed_action_ids"] = draw(st.lists(TEXT, max_size=10) | big)
    state["archivist_last_run"] = draw(st.integers(0, 10_000))
    state["conflict_summary"] = draw(CONFLICT)
    state["messages"] = draw(MESSAGES)
    return state


def _save_load(state: dict[str, Any]) -> dict[str, Any]:
    assert persistence.save_game_state(state) is True
    return persistence.load_game_state(persistence.save_path(state["game_id"]))


def _msgs(messages: list[Any]) -> list[tuple[str, str]]:
    return [(type(m).__name__, str(m.content)) for m in messages]


@deterministic_settings(max_examples=20)
@given(s0=states())
def test_rt1_save_load_preserves_mutated_fields(s0: dict[str, Any]) -> None:
    """RT1: cada campo mutado volta igual, salvo as normalizações documentadas."""
    s1 = _save_load(s0)
    p0, p1 = s0["player"], s1["player"]
    for key in ("gold", "vitalidade", "inventory"):
        assert p1[key] == p0[key], key
    assert set(p1) - set(p0) <= PLAYER_EXTRA
    assert set(s1["world"]) - set(s0["world"]) <= WORLD_EXTRA
    assert s1["world"]["turn_count"] == s0["world"]["turn_count"]
    assert s1["processed_action_ids"] == s0["processed_action_ids"][-64:]
    assert s1["archivist_last_run"] == s0["archivist_last_run"]
    assert _msgs(s1["messages"]) == _msgs(s0["messages"])
    c0, c1 = s0["conflict_summary"], s1["conflict_summary"]
    if c0 is None:
        assert c1 is None
    else:
        assert {k: v for k, v in c1.items() if k in c0} == c0
        assert set(c1) - set(c0) <= {"conflict_id", "conflict_turn"}


@deterministic_settings(max_examples=20)
@given(s0=states())
def test_rt2_save_load_is_idempotent_after_first_pass(s0: dict[str, Any]) -> None:
    """RT2: `load(save(s1)) == s1` — depois da 1ª normalização o round-trip é ponto fixo."""
    s1 = _save_load(s0)
    s2 = _save_load(s1)
    assert {k: v for k, v in s2.items() if k != "messages"} == {
        k: v for k, v in s1.items() if k != "messages"
    }
    assert _msgs(s2["messages"]) == _msgs(s1["messages"])


@deterministic_settings(max_examples=20)
@given(s0=states())
def test_rt3_save_does_not_mutate_input(s0: dict[str, Any]) -> None:
    """RT3: `save_game_state` não muta o estado de entrada."""
    before = copy.deepcopy(s0)
    persistence.save_game_state(s0)
    assert {k: v for k, v in s0.items() if k != "messages"} == {
        k: v for k, v in before.items() if k != "messages"
    }
    assert _msgs(s0["messages"]) == _msgs(before["messages"])
