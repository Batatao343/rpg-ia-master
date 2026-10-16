"""SPEC-229 — parsers de intenção (viagem, fuga, router, validador de prosa)."""
import json
import pathlib

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import gamedata
from agents.router import dm_router_node
from world_utils import find_travel_destination, is_travel_intent

CORPUS = json.loads(
    (pathlib.Path(__file__).parent / "data" / "intent_corpus.json").read_text(encoding="utf-8")
)


def _world(loc="nova_arcadia"):
    node = gamedata.get_location(loc)
    return {"current_location_id": loc, "current_location": node["name"],
            "visited": [loc], "world_clock": {"day": 1, "period": "manha"}}


@pytest.mark.parametrize("text", CORPUS["travel_pos"])
def test_travel_pos(text):
    assert is_travel_intent(text, _world()) is True


@pytest.mark.parametrize("text", CORPUS["travel_neg"])
def test_travel_neg(text):
    assert is_travel_intent(text, _world()) is False


def test_vou_ao_finds_destination_and_travels():
    from agents.storyteller import storyteller_node
    w = _world()
    dest = find_travel_destination(w, "Vou ao Pântano da Melancolia")
    assert dest and dest["id"] == "pantano_melancolia"
    out = storyteller_node(_state(w, "Vou ao Pântano da Melancolia"))
    assert out["world"]["current_location_id"] == "pantano_melancolia"


def _state(world, text):
    from state import GameState  # noqa: F401
    return {"world": world, "messages": [HumanMessage(content=text)], "player": {
        "name": "T", "class_name": "Devoto do Abismo", "race": "Humano", "hp": 30, "max_hp": 30,
        "gold": 10, "level": 1, "xp": 0, "inventory": [], "equipment": {}},
        "npcs": {}, "enemies": [], "game_id": "t229"}


def test_local_movement_not_refused():
    from agents.storyteller import storyteller_node
    out = storyteller_node(_state(_world(), "Entro na taverna e peço uma bebida"))
    content = out["messages"][0].content
    assert "Não há rota direta" not in content


def test_unknown_toponym_refused():
    from agents.storyteller import storyteller_node
    out = storyteller_node(_state(_world(), "Vou para Atlântida"))
    assert "Não há rota direta" in out["messages"][0].content


@pytest.mark.parametrize("text,route", list(CORPUS["story_not_story"].items()))
def test_router_precedence(text, route):
    out = dm_router_node({"world": _world(), "messages": [HumanMessage(content=text)]})
    assert out["next"] == route


@pytest.mark.parametrize("text", CORPUS["story_ok"])
def test_router_story(text):
    out = dm_router_node({"world": _world(), "messages": [HumanMessage(content=text)]})
    assert out["next"] == "storyteller"


@pytest.mark.parametrize("text", CORPUS["flee_neg"])
def test_flee_neg(text):
    from services.chase import FLEE_RE
    assert not FLEE_RE.search(text.lower())


@pytest.mark.parametrize("text", CORPUS["flee_pos"])
def test_flee_pos(text):
    from services.chase import FLEE_RE
    assert FLEE_RE.search(text.lower())


def test_narrative_validator_sentence_scope():
    from services.conflict_summary import validate_narrative_text
    s = {"mortos": ["Goblin 1"]}
    ok = validate_narrative_text(s, "Goblin 1 desaba no chão; o vento escapa pelas frestas.")
    assert ok["ok"]
    bad = validate_narrative_text(s, "Goblin 1 ainda vivo rasteja pelo chão.")
    assert not bad["ok"]


@pytest.mark.parametrize("text,expected", [
    ("Quero descansar", True), ("Vamos dormir aqui", True), ("Descanso na clareira", True),
    ("Compro uma barraca de acampar", False), ("Compro um saco de dormir", False),
    ("Falo com a viajante", False),
])
def test_story_shortcut_infinitives_need_auxiliary(text, expected):
    from agents.router import _EXPLICIT_STORY_RE
    assert bool(_EXPLICIT_STORY_RE.search(text)) is expected


@pytest.mark.parametrize("text,expected", [
    ("fuja!", True), ("recuamos", True), ("nos retiramos", True), ("corro de volta", True),
    ("recuperar a espada", False), ("recuso", False), ("retirar a flecha", False),
    ("corro até o orc", False),
])
def test_flee_regex_common_forms(text, expected):
    from services.chase import FLEE_RE
    assert bool(FLEE_RE.search(text)) is expected
