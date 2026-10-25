"""SPEC-313 Etapa 4: caca (prova por combate) e encontros (R26/R27)."""

from __future__ import annotations

import copy

import pytest

import gamedata
import world_utils
from services import event_processor as ep
from services import lore_quests as lq
from services import quest_log
from services import world_quests as wq
from tests.spec313_helpers import NPC_KEY, first_anchor, npc_state, proposal, setup_env


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def _hunt_state(created_turn=17):
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "cacar_criatura")
    quests, created, _r = wq.offer_from_proposal(
        st, proposal("cacar_criatura", aid), NPC_KEY, menu, 17
    )
    created["created_turn"] = created_turn
    st["quests"] = [created]
    st["player"] = {"name": "H", "level": 1, "xp": 0, "gold": 10, "inventory": []}
    return st, created, aid


def test_hunt_completes_on_anchor_kill_in_region():
    st, quest, aid = _hunt_state()
    st["world"]["turn_count"] = 19
    st["quests"] = quest_log.sync_hunt_progress(st["quests"], [aid], "skallgard", turn=19)
    assert [r for r in st["quests"][0]["progress_log"] if r["kind"] == "hunt_kill"]
    events = wq.engine_completions(st)
    assert len(events) == 1 and events[0]["type"] == "quest_completed"
    assert events[0]["source"] == "engine"
    out = ep.process_pending_events({**st, "pending_world_events": events})
    done = out["quests"][0]
    assert done["status"] == "completed" and done["reward_gold"] == 15
    assert out["player"]["gold"] == 10 + 15


def test_hunt_ignores_other_species_region_and_creation_turn():
    st, quest, aid = _hunt_state()
    base = copy.deepcopy(st["quests"])
    assert quest_log.sync_hunt_progress(base, ["enemy_outro"], "skallgard", turn=19) == base
    assert quest_log.sync_hunt_progress(base, [aid], "brekmar", turn=19) == base
    assert quest_log.sync_hunt_progress(base, [aid], "skallgard", turn=17) == base  # mesmo turno
    assert (
        quest_log.sync_hunt_progress(base, [], "skallgard", turn=19) == base
    )  # fugiu: ninguem morreu


def test_hunt_counts_once_per_combat():
    st, _q, aid = _hunt_state()
    once = quest_log.sync_hunt_progress(st["quests"], [aid, aid], "skallgard", turn=19)
    twice = quest_log.sync_hunt_progress(once, [aid], "skallgard", turn=20)
    assert twice == once
    assert len([r for r in twice[0]["progress_log"] if r["kind"] == "hunt_kill"]) == 1


def test_llm_cannot_complete_hunt_without_the_kill():
    st, quest, _aid = _hunt_state()
    st["world"]["turn_count"] = 25
    st["quests"][0]["progress_log"].append({"kind": "location_reached", "turn": 18, "detail": ""})
    st["quests"][0]["progress_log"].append({"kind": "investigation", "turn": 19, "detail": "x"})
    ok, why = quest_log.has_completion_proof(st["quests"][0], st)
    assert not ok and "mecânica" in why
    # e nenhuma "investigacao" fecha a caca
    _q, ready = quest_log.sync_action_progress(
        st["quests"], "skallgard", "caço e rastreio", turn=26
    )
    assert ready == []


def _small_loc():
    loc = gamedata.get_location("skallgard")
    return loc


def test_encounter_theme_prefers_anchor_when_encounter_fires():
    loc = _small_loc()
    pool = [
        e
        for e in gamedata.BESTIARY.values()
        if "skallgard" in e.get("regions", []) and "elite" not in str(e.get("type", "")).lower()
    ]
    target = next(e["id"] for e in pool if e.get("categoria") == "lacaio")
    picks = {
        world_utils.pick_encounter_enemy(loc, 2, turn, theme=world_utils.hunt_theme(target))["id"]
        for turn in range(12)
    }
    assert picks == {target}
    assert world_utils.hunt_theme("") is None


def test_anchor_above_porte_falls_back_to_normal_pick():
    loc = _small_loc()
    elite = next(
        e["id"]
        for e in gamedata.BESTIARY.values()
        if "skallgard" in e.get("regions", [])
        and "elite" in str(e.get("type", "")).lower()
        and e.get("categoria") == "elite"
    )
    pick = world_utils.pick_encounter_enemy(loc, 1, 3, theme=world_utils.hunt_theme(elite))
    assert pick is not None and pick["id"] != elite  # perigo 1 => so Minion: sorteio normal
    assert world_utils.pick_encounter_enemy(loc, 1, 3)["id"] == pick["id"]


def test_no_new_encounter_trigger_with_hunt_active():
    """R26: a ancora so entra no SORTEIO de um encontro que ja disparou."""
    ids = [
        loc["id"] for loc in gamedata.WORLD_MAP["locations"] if int(loc.get("danger", 1) or 1) >= 4
    ][:3]
    assert ids
    for lid in ids:
        region = gamedata.get_location(lid)["region_id"]
        anchor = next(
            e["id"]
            for e in gamedata.BESTIARY.values()
            if region in e.get("regions", []) and e.get("categoria") == "lacaio"
        )
        for turn in range(0, 40, 3):
            world = {"current_location_id": lid, "last_encounter_turn": -99}
            a = world_utils.check_encounter(copy.deepcopy(world), [], {}, turn, player_level=5)
            b = world_utils.check_encounter(
                copy.deepcopy(world), [], {}, turn, player_level=5, hunt_anchor=anchor
            )
            assert (a is None) == (b is None)
            if a:
                assert a["reason"] == b["reason"]


def test_active_hunt_anchor_reads_only_active_regional_quest():
    st, quest, aid = _hunt_state()
    assert lq.active_hunt_anchor(st) == aid
    st["quests"][0]["status"] = "completed"
    assert lq.active_hunt_anchor(st) == ""
