"""SPEC-313 Etapa 3: oferta, prazo, recompensa e anti-farm."""

from __future__ import annotations

import pytest

from services import lore_quests as lq
from services import world_quests as wq
from tests.spec313_helpers import NPC_KEY, first_anchor, npc_state, proposal, setup_env


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def _hunt(st, day=17):
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    aid = first_anchor(menu, "cacar_criatura")
    return wq.offer_from_proposal(st, proposal("cacar_criatura", aid), NPC_KEY, menu, day), aid


def test_offer_from_proposal_builds_world_quest_with_heard_via_npc():
    st = npc_state()
    (quests, created, reason), aid = _hunt(st)
    assert reason == "" and quests == [created]
    assert created["world_kind"] == "cacar_criatura"
    assert created["heard_via"] == {"channel": "npc", "event_id": "npc:npc_rolf:17", "day": 17}
    assert created["origin_name"] == "Rolf" and created["lore_origin_key"] == "npc_rolf"
    assert created["lore_anchor"]["id"] == aid and created["lore_ref"].startswith("lore_nova/")
    assert created["status"] == "active" and created["deadline_day"] == 17 + 6


def test_deadline_rules_per_kind():
    assert lq.deadline_for({}, "cacar_criatura", {}, 10) == 16
    assert lq.deadline_for({}, "entregar_material", {"periods": 1}, 10) == 10 + 2 + 2
    assert lq.deadline_for({}, "entregar_material", {"periods": 6}, 10) == 10 + 4 + 2
    assert lq.deadline_for({}, "escoltar", {"periods": 6}, 10) == 10 + 2 + 2
    assert lq.deadline_for({}, "investigar_rumor", {}, 10) == 18
    assert lq.deadline_for({}, "investigar_rumor", {"ttl_day": 13}, 10) == 13
    assert lq.deadline_for({}, "recolher_mortos", {}, 10) == 14


def test_deadline_never_shortens_after_creation():
    st = npc_state()
    (quests, created, _r), _aid = _hunt(st)
    st["quests"] = quests
    st["world_sim"]["last_ticked_day"] = 18
    out, events = wq.sync_deadlines(st, 18)
    assert out[0]["deadline_day"] == created["deadline_day"] and events == []


def test_reward_by_categoria_and_distance_band():
    assert lq.reward_for("cacar_criatura", {"categoria": "lacaio"}, "x") == (15, "modesta")
    assert lq.reward_for("cacar_criatura", {"categoria": "padrao"}, "x") == (25, "justa")
    assert lq.reward_for("cacar_criatura", {"categoria": "elite"}, "x") == (40, "generosa")
    assert lq.reward_for("entregar_material", {"periods": 5}, "x")[0] == 15
    assert lq.reward_for("entregar_material", {"periods": 12}, "x")[0] == 25
    assert lq.reward_for("entregar_material", {"periods": 30}, "x")[0] == 40
    assert lq.reward_for("escoltar", {"periods": 5}, "x")[0] == 20
    assert lq.reward_for("investigar_rumor", {}, "npc_rolf") == (10, "modesta")
    assert lq.reward_for("investigar_rumor", {}, "engine") == (0, "")
    assert lq.reward_for("recolher_mortos", {}, "engine")[0] == 15


def test_reward_label_no_number():
    for gold in (10, 15, 20, 25, 30, 40, 45):
        label = lq.cfg()["reward_labels"][str(gold)]
        assert label and not any(ch.isdigit() for ch in label)


def test_one_per_source_any_status():
    st = npc_state()
    (quests, created, _r), aid = _hunt(st)
    st["quests"] = [{**created, "status": "failed", "resolved_day": 18}]
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    p = proposal("cacar_criatura", aid)
    _q, again, reason = wq.offer_from_proposal(st, p, NPC_KEY, menu, 40)
    assert again is None and reason in {"not_in_menu", "source_used", "origin_cooldown"}


def test_origin_cooldown_and_anchor_cooldown_in_days():
    st = npc_state()
    (quests, created, _r), aid = _hunt(st)
    st["quests"] = [{**created, "status": "completed", "resolved_day": 19}]
    anchor = {"type": "enemy", "id": aid, "region_id": "skallgard"}
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "npc_rolf", 20) == "origin_cooldown"
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "outro", 20) == "anchor_cooldown"
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "outro", 28) == "anchor_cooldown"
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "outro", 29) == ""
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "npc_rolf", 24) == "anchor_cooldown"
    assert lq.on_cooldown(st, "cacar_criatura", anchor, "npc_rolf", 30) == ""


def test_lore_cap_two_and_global_cap():
    st = npc_state()
    base = {"status": "active", "world_kind": "cacar_criatura"}
    st["quests"] = [{**base, "id": "a"}, {**base, "id": "b"}]
    assert lq.cap_reached(st)
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    _q, created, reason = wq.offer_from_proposal(
        st, proposal("cacar_criatura", first_anchor(menu, "cacar_criatura")), NPC_KEY, menu, 17
    )
    assert created is None and reason == "cap"
    # teto proprio: 3 quests de crise ativas NAO ocupam as vagas de lore
    st["quests"] = [
        {"status": "active", "world_kind": "romper_cerco", "id": str(i)} for i in range(3)
    ]
    assert not lq.cap_reached(st)
    assert wq._active_world(st["quests"]) == 3


def test_infeasible_not_offered(monkeypatch):
    st = npc_state()
    _b, menu = lq.anchor_menu(st, NPC_KEY)
    monkeypatch.setattr(wq, "is_feasible", lambda *a, **k: False)
    _q, created, reason = wq.offer_from_proposal(
        st, proposal("cacar_criatura", first_anchor(menu, "cacar_criatura")), NPC_KEY, menu, 17
    )
    assert created is None and reason == "infeasible"


def test_deterministic_ids_and_idempotent_offer():
    a, b = npc_state(), npc_state()
    (_q1, c1, _), _ = _hunt(a)
    (_q2, c2, _), _ = _hunt(b)
    assert c1["id"] == c2["id"] and c1 == c2
    a["quests"] = [c1]
    _b, menu = lq.anchor_menu(a, NPC_KEY)
    assert not [i for i in menu if i["anchor_id"] == c1["lore_anchor"]["id"]]


def test_complete_uses_planned_reward_not_flat_20():
    from services import quest_log

    st = npc_state()
    (_q, created, _r), _aid = _hunt(st)
    done, gold = quest_log.complete_quest_with_reward([created], created["id"], 20)
    assert gold == 15 and done[0]["reward_gold"] == 15
