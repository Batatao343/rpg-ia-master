"""SPEC-313 Etapa 8: rollout, invariantes, mock e cenario dirigido."""

from __future__ import annotations

from playtest import invariants
from services import lore_quests as lq
from services import world_quests as wq
from tests.spec313_helpers import NPC_KEY, first_anchor, npc_state, proposal, setup_env


def _ids(violations):
    return {v.check_id for v in violations}


def test_mode_off_downgrades_and_hides_menu(monkeypatch):
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "cacar_criatura")
    setup_env(monkeypatch, lore="off")
    assert lq.anchor_menu(st, NPC_KEY) == ("", [])
    quests, created, reason = wq.offer_from_proposal(
        st, proposal("cacar_criatura", aid), NPC_KEY, menu, 17
    )
    assert created is None and reason == "mode_off" and reason in lq.DOWNGRADE_REASONS


def test_shadow_writes_nothing(monkeypatch):
    setup_env(monkeypatch, lore="shadow")
    st = npc_state()
    assert lq.anchor_menu(st, NPC_KEY) == ("", [])
    from tests.spec313_helpers import add_rumor

    st2 = npc_state(loc="nova_arcadia")
    st2["npcs"] = {}
    add_rumor(st2)
    quests, created = wq.offer_from_heard(st2, 17)
    assert created == [] and not [q for q in quests if q.get("world_kind")]


def test_requires_world_quests_on(monkeypatch):
    setup_env(monkeypatch)
    assert lq.mode() == "on"
    monkeypatch.setenv("RPG_WORLD_QUESTS", "off")
    assert lq.mode() == "off"
    monkeypatch.setenv("RPG_WORLD_QUESTS", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    assert lq.mode() == "off"


def test_invariants_detect_anchor_invalid_cooldown_truth_leak_escort_split(monkeypatch):
    setup_env(monkeypatch)
    st = npc_state()
    base = {"status": "active", "heard_via": {"channel": "npc", "event_id": "npc:x:1"}}
    bad_anchor = {
        **base,
        "id": "a",
        "world_kind": "cacar_criatura",
        "lore_anchor": {"id": "enemy_nada"},
    }
    st["quests"] = [bad_anchor]
    assert "quest.lore_anchor_invalid" in _ids(invariants.check_lore_quests(st, None, 3))

    good = {"type": "enemy", "id": "enemy_lobo_invernal"}
    twice = [
        {
            **base,
            "id": "a",
            "world_kind": "cacar_criatura",
            "lore_anchor": good,
            "lore_ref": "x",
            "lore_origin_key": "npc_rolf",
            "created_day": 10,
        },
        {
            **base,
            "id": "b",
            "world_kind": "cacar_criatura",
            "lore_anchor": good,
            "lore_ref": "x",
            "lore_origin_key": "npc_rolf",
            "created_day": 12,
        },
    ]
    st["quests"] = twice
    assert "quest.lore_cooldown_violated" in _ids(invariants.check_lore_quests(st, None, 3))

    leak = {
        **base,
        "id": "c",
        "world_kind": "investigar_rumor",
        "outcome": "desmentido",
        "lore_anchor": {"id": "r1"},
        "lore_ref": "x",
        "lore_origin_key": "engine",
    }
    st["quests"] = [leak]
    assert "quest.rumor_truth_leaked" in _ids(invariants.check_lore_quests(st, None, 3))

    st["quests"] = []
    st["npc_sim"]["npcs"]["npc_rolf"]["escort"] = {
        "quest_id": "q",
        "to": "brekmar",
        "paused_at": "",
    }
    st["npc_sim"]["npcs"]["npc_rolf"]["pos"]["location_id"] = "brekmar"
    assert "quest.escort_split" not in _ids(invariants.check_lore_quests(st, None, 3))
    st["quests"] = [
        {
            **base,
            "id": "q",
            "world_kind": "escoltar",
            "lore_anchor": {"id": "npc_rolf"},
            "lore_ref": "x",
            "lore_origin_key": "npc_rolf",
            "created_day": 1,
        }
    ]
    assert "quest.escort_split" in _ids(invariants.check_lore_quests(st, None, 3))


def test_invariant_delivery_without_item(monkeypatch):
    setup_env(monkeypatch)
    anchor = {"type": "route", "id": "cha_druidas_anel_lama", "item_id": "musgo_cinzento", "qty": 2}
    q = {
        "id": "d",
        "world_kind": "entregar_material",
        "lore_anchor": anchor,
        "lore_ref": "x",
        "lore_origin_key": "npc_rolf",
        "created_day": 1,
    }
    prev = npc_state()
    prev["quests"] = [{**q, "status": "active"}]
    prev["player"] = {"inventory": [{"id": "musgo_cinzento", "qty": 2}]}
    now = npc_state()
    now["quests"] = [{**q, "status": "completed"}]
    now["player"] = {"inventory": [{"id": "musgo_cinzento", "qty": 2}]}
    assert "quest.delivery_without_item" in _ids(invariants.check_lore_quests(now, prev, 4))
    now["player"] = {"inventory": []}
    assert "quest.delivery_without_item" not in _ids(invariants.check_lore_quests(now, prev, 4))


def test_mock_npc_proposes_from_menu(monkeypatch):
    from langchain_core.messages import HumanMessage, SystemMessage

    import mock_llm

    setup_env(monkeypatch)
    block, menu = lq.anchor_menu(npc_state(), NPC_KEY)
    out = mock_llm._mock_lore_quest([SystemMessage(content=block), HumanMessage(content="oi")])
    assert out and out[0]["kind"] == menu[0]["kind"] and out[0]["anchor_id"] == menu[0]["anchor_id"]
    assert mock_llm._mock_lore_quest([HumanMessage(content="oi")]) == []


def test_scenario_lore_quests_offers_hunt(monkeypatch):
    """Cenario dirigido (MockLLM): conversa com o cacador -> quest ancorada criada pelo motor."""
    from playtest.runner import run_campaign

    result = run_campaign("explorador", turns=3, seed=31, scenario="lore_quests")
    assert not [v for v in result.violations if v.get("severity") == "error"], result.violations
    quests = [
        q for q in result.final_state.get("quests", []) if q.get("world_kind") in lq.LORE_KINDS
    ]
    assert quests and quests[0]["heard_via"]["channel"] == "npc"
