"""SPEC-357 R11-R13 - Tecnica (Carta neutra) como recompensa de quest de lore."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from services import card_rewards as cr
from services import cards, quest_log, world_quests
from services.event_processor import process_pending_events


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "on")


def _seed(label="justa", gold=25):
    return SimpleNamespace(
        kind="cacar_criatura",
        anchor={},
        origin_key="engine",
        reward_gold=gold,
        reward_label=label,
        llm_title="",
        llm_description="",
    )


def _quest(qid="q1", label="justa", location="brekmar", planned=True):
    q = {
        "id": qid,
        "title": "Caça",
        "status": "active",
        "created_turn": 1,
        "location_id": location,
        "reward_gold_planned": 25,
        "reward_hint": f"{label} · uma técnica" if planned else label,
        "progress_log": [
            {"kind": "location_reached", "turn": 1},
            {"kind": "investigation", "turn": 2},
        ],
    }
    if planned:
        q["reward_card_planned"] = True
        q["reward_card_label"] = label
    return q


def _state(quest, level=6):
    ev = {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": quest["id"],
        "payload": {"quest_id": quest["id"]},
        "source": "storyteller",
    }
    return {
        "game_id": "g",
        "player": {
            "xp": 0,
            "gold": 0,
            "level": level,
            "name": "A",
            "class_name": "Sangromante",
            "known_cards": [],
            "deck": [],
            "prepared_cards": [],
        },
        "world": {"turn_count": 5},
        "event_log": [],
        "world_projection": {},
        "quests": [quest],
        "pending_world_events": [ev, copy.deepcopy(ev)],
    }


def test_planned_only_for_listed_labels(monkeypatch):
    assert world_quests._lore_fields(_seed("justa"))["reward_card_planned"] is True
    assert world_quests._lore_fields(_seed("generosa", 40))["reward_card_planned"] is True
    assert "reward_card_planned" not in world_quests._lore_fields(_seed("modesta", 15))
    assert "reward_card_planned" not in world_quests._lore_fields(_seed("", 0))
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    f = world_quests._lore_fields(_seed("justa"))
    assert "reward_card_planned" not in f and f["reward_hint"] == "justa"


def test_reward_hint_suffix():
    assert (
        world_quests._lore_fields(_seed("generosa", 40))["reward_hint"] == "generosa · uma técnica"
    )


def test_grant_on_completion_regional_first():
    q = _quest(location="brekmar")
    out = process_pending_events(_state(q))
    got = [c for c in out["player"]["known_cards"] if c.startswith("neu1_")]
    assert len(got) == 1
    card = cards.get_card(got[0])
    assert cards.is_neutral(card) and card.get("regiao") in (None, "", "brekmar")
    done = next(x for x in out["quests"] if x["id"] == "q1")
    assert done["reward_card"] == got[0]


def test_grant_same_player_as_xp_gold():
    out = process_pending_events(_state(_quest()))
    p = out["player"]
    assert p["xp"] > 0 and p["gold"] > 0 and p["known_cards"]


def test_grant_deterministic_by_quest_id():
    a = process_pending_events(_state(_quest("qx")))["player"]["known_cards"]
    b = process_pending_events(_state(_quest("qx")))["player"]["known_cards"]
    assert a == b


def test_grant_once_only():
    out = process_pending_events(_state(_quest()))  # 2 eventos iguais no lote
    assert len(out["player"]["known_cards"]) == 1
    assert len([n for n in out["reputation_notices"] if n["kind"] == "carta"]) == 1


def test_grant_skips_known_and_empty_pool():
    player = {"level": 6, "known_cards": []}
    q = _quest()
    first = cr.grant_for_quest({}, dict(player), q, 5)
    assert first
    allc = [c for c, v in cards.all_cards().items() if cards.is_neutral(v)]
    known = {"level": 6, "known_cards": allc}
    assert cr.grant_for_quest({}, known, q, 5) is None
    again = cr.grant_for_quest({}, {"level": 6, "known_cards": [first]}, q, 5)
    assert again != first


def test_notice_kind_carta():
    out = process_pending_events(_state(_quest()))
    note = next(n for n in out["reputation_notices"] if n["kind"] == "carta")
    assert note["text"].startswith("Você aprende ") and note["text"].endswith("com a missão.")
    assert note["subject_id"] in out["player"]["known_cards"]


def test_public_view_reward_card_name_only():
    out = process_pending_events(_state(_quest()))
    done = next(x for x in out["quests"] if x["id"] == "q1")
    view = quest_log.public_quest_view(done, 5)
    assert view["reward_card_name"] == cards.get_card(done["reward_card"])["name"]
    assert "reward_card_planned" not in view and "reward_card" not in view
    assert "reward_card_name" not in quest_log.public_quest_view(_quest(planned=False), 5)


def test_old_quest_without_planned_no_card():
    out = process_pending_events(_state(_quest(planned=False)))
    assert out["player"]["known_cards"] == [] and out["player"]["gold"] > 0


def test_shadow_writes_nothing(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "shadow")
    out = process_pending_events(_state(_quest()))
    assert out["player"]["known_cards"] == []
    done = next(x for x in out["quests"] if x["id"] == "q1")
    assert "reward_card" not in done


def test_off_writes_nothing(monkeypatch):
    monkeypatch.setenv("RPG_CARD_REWARDS", "off")
    out = process_pending_events(_state(_quest()))
    assert out["player"]["known_cards"] == []
