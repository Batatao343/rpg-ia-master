"""SPEC-379 R2: fabricas de estado (paridade com POST /game/new)."""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import api
import character_creator
import persistence
from tests.factories import make_player, make_state, make_world

_UUID_A = UUID("00000000-0000-4000-8000-000000000379")
_UUID_B = UUID("00000000-0000-4000-8000-000000000380")
_BODY = {
    "name": "Herói",
    "race": "Humano",
    "class_name": "Devoto do Abismo",
    "region": "Nova Arcádia",
}


def _capture_api_state(monkeypatch, fixed: UUID, **extra) -> dict:
    captured: dict = {}

    class Graph:
        def invoke(self, current):
            captured.update(current)
            return current

    monkeypatch.setattr(api, "game_graph", Graph())
    monkeypatch.setattr(api.uuid, "uuid4", lambda: fixed)
    resp = TestClient(api.app).post("/game/new", json={**_BODY, **extra})
    assert resp.status_code == 200, resp.text
    return captured


def _msgs(state: dict) -> list[tuple[str, str]]:
    return [(type(m).__name__, m.content) for m in state["messages"]]


def _assert_same(factory: dict, produced: dict) -> None:
    assert set(factory) == set(produced)
    assert set(factory["player"]) == set(produced["player"])
    assert factory["player"] == produced["player"]
    assert factory["world"] == produced["world"]
    assert factory.get("world_sim") == produced.get("world_sim")
    assert factory["narrative_summary"] == produced["narrative_summary"]
    assert _msgs(factory) == _msgs(produced)
    for key in set(factory) - {"messages"}:
        assert factory[key] == produced[key], key


def test_make_state_matches_api_new_game(monkeypatch):
    produced = _capture_api_state(monkeypatch, _UUID_A)
    _assert_same(make_state(game_id=str(_UUID_A)), produced)


def test_level_3_matches_api_level_3(monkeypatch):
    produced = _capture_api_state(monkeypatch, _UUID_A, level=3)
    _assert_same(make_state(game_id=str(_UUID_A), level=3), produced)


def test_calendar_follows_game_id(monkeypatch):
    cals = []
    for uid in (_UUID_A, _UUID_B):
        produced = _capture_api_state(monkeypatch, uid)
        mine = make_state(game_id=str(uid))
        assert mine["world_sim"]["calendar"] == produced["world_sim"]["calendar"]
        cals.append(mine["world_sim"]["calendar"])
    assert cals[0] != cals[1]


def test_make_state_is_isolated():
    first = make_state()
    first["player"]["inventory"].append("lixo")
    first["player"]["virtudes"]["x"] = 1
    first["world"]["turn_count"] = 99
    second = make_state()
    assert "lixo" not in second["player"]["inventory"]
    assert "x" not in second["player"]["virtudes"]
    assert second["world"]["turn_count"] != 99


def test_make_state_never_calls_llm(monkeypatch):
    from tests import factories

    def boom(*a, **k):
        raise AssertionError("get_llm chamado")

    monkeypatch.setattr(character_creator, "get_llm", boom)
    factories._sheet.cache_clear()
    try:
        assert make_state(class_name="Devoto do Abismo")["player"]["class_name"]
    finally:
        factories._sheet.cache_clear()


def test_make_state_round_trip_save_load():
    state = make_state(game_id=str(uuid.uuid4()))
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(state["game_id"]))
    # load_game_state religa sync_vitality: unica chave que ele acrescenta ao player
    extra = {k: v for k, v in loaded["player"].items() if k not in state["player"]}
    assert set(extra) <= {"vitalidade_base_bonus"}
    assert {k: v for k, v in loaded["player"].items() if k in state["player"]} == state["player"]
    # load acrescenta defaults de campos novos do mundo (ex.: shelter=None); nada some nem muda
    assert {k: v for k, v in loaded["world"].items() if k in state["world"]} == state["world"]
    assert {k: v for k, v in loaded["world"].items() if k not in state["world"]} == {
        "shelter": None
    }


def test_overrides_merge_player_world_replace_top():
    base = make_state()
    st = make_state(player={"gold": 7}, world={"turn_count": 5}, factions=[], quests=["q"])
    assert st["player"]["gold"] == 7
    assert st["player"]["name"] == base["player"]["name"]
    assert st["world"]["turn_count"] == 5
    assert st["world"]["current_location"] == base["world"]["current_location"]
    assert st["factions"] == [] and st["quests"] == ["q"]


def test_game_id_goes_to_named_parameter():
    assert make_state(game_id="abc")["game_id"] == "abc"
    with pytest.raises(TypeError):
        make_state(game_id="x", **{"game_id": "y"})  # type: ignore[call-overload]


def test_make_player_and_world_blocks():
    assert make_player(gold=3)["gold"] == 3
    assert make_world(turn_count=2)["turn_count"] == 2
