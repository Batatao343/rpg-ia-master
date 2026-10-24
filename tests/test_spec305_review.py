"""SPEC-305: correcoes da revisao Sol (P1-1, P1-2, P2-1..P2-6)."""

from __future__ import annotations

import random

from langchain_core.messages import AIMessage

from services import quest_log as ql
from services import reputation
from services import world_director as wd
from services import world_engine as we
from services import world_quests as wq
from services.world_validators import validate_proposal
from tests.spec302_helpers import quiet, set_pressure
from tests.spec305_helpers import GID, add_crisis, base_state, crisis_item


def _quest() -> dict:
    state = base_state()
    add_crisis(state)
    _q, created = wq.offer_from_perceived(state, [crisis_item()], 17)
    return created[0]


def test_failed_and_expired_world_quest_share_one_public_dict():
    base = _quest()
    a = ql.public_quest_view({**base, "status": "failed", "fail_reason": "prazo"}, 30)
    b = ql.public_quest_view({**base, "status": "expired", "fail_reason": "superada"}, 30)
    assert a == b and a["status"] == "expired"
    common = {"id": "c", "title": "x", "status": "failed"}
    assert ql.public_quest_view(common, 30)["status"] == "failed"  # quest comum nao muda


def test_completion_rejected_on_deadline_day_unless_engine():
    q = {**_quest(), "created_turn": 1}
    q["progress_log"] = [
        {"kind": "location_reached", "turn": 2},
        {"kind": "investigation", "turn": 3, "fingerprint": "tratar doentes"},
    ]
    state = base_state(day=q["deadline_day"])
    state["quests"] = [q]
    state["world"]["turn_count"] = 9
    prop = {"type": "quest_completed", "target_id": q["id"], "payload": {"quest_id": q["id"]}}
    for src in ("storyteller", "system"):
        res = validate_proposal({**prop, "source": src}, state)
        assert not res.ok and "prazo" in res.reason
    assert validate_proposal({**prop, "source": "engine"}, state).ok
    # um dia antes do prazo a mesma prova vale
    state["world"]["world_clock"]["day"] = q["deadline_day"] - 1
    assert validate_proposal({**prop, "source": "system"}, state).ok


def test_unheard_invariant_rejects_plain_logged_event_for_crisis_quest():
    from playtest import invariants as inv

    state = base_state()
    add_crisis(state)
    q = _quest()
    q["heard_via"] = {"channel": "testemunho", "event_id": "ev-motor", "day": 17}
    state["quests"] = [q]
    state["event_log"] = [{"event_id": "ev-motor", "type": "location_state_changed"}]
    assert "quest.world_unheard" in {v.check_id for v in inv.check_world_quests(state, None, 1)}
    state["world_sim"]["perceived_ids"] = ["ev-motor"]
    assert inv.check_world_quests(state, None, 1) == []


def test_relieved_crisis_closes_after_max_days_even_if_pressure_stays_high():
    cfg = quiet()
    sim = we._new_sim(GID, 17, [], "on")
    sim["calm_until_day"] = 0
    sim["crises"].append(
        {
            "crisis_id": "c",
            "kind": "praga",
            "region_id": "brekmar",
            "location_id": "brekmar",
            "loc_state": "praga",
            "faction_id": "",
            "warned_day": 10,
            "start_day": 12,
            "escalation_day": 40,
            "severity": 1,
            "end_day": None,
            "resolution": "",
        }
    )
    set_pressure(sim, "brekmar", "praga", 95)
    wd.relieve(sim, "c", 16)
    wd.step_crises(sim, 20, {}, random.Random(1), game_id=GID, cfg=cfg)
    assert sim["crises"][0]["end_day"] is None
    wd.step_crises(sim, 24, {}, random.Random(1), game_id=GID, cfg=cfg)
    assert sim["crises"][0]["resolution"] == "intervencao"


def test_save_load_roundtrip_of_world_quest_fields(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    state = base_state()
    add_crisis(state)
    state["world_sim"]["crises"][0]["relieved_day"] = 18
    state["world_sim"]["perceived_ids"] = ["ev-open-1"]
    state["world_projection"] = {
        "location_states": {
            "nova_arcadia": {"state": "ocupado", "liberation_day": 18, "consolidated_until_day": 40}
        }
    }
    state["quests"] = [_quest()]
    state["messages"] = [AIMessage(content="oi")]
    state["player"] = {"inventory": []}
    assert persistence.save_game_state(state)
    back = persistence.load_game_state(str(tmp_path / f"{GID}.json"))
    q = back["quests"][0]
    for key in ("world_kind", "world_source_id", "deadline_day", "heard_via", "fail_text"):
        assert q[key] == state["quests"][0][key]
    assert back["world_sim"]["crises"][0]["relieved_day"] == 18
    assert back["world_sim"]["perceived_ids"] == ["ev-open-1"]
    row = back["world_projection"]["location_states"]["nova_arcadia"]
    assert row["liberation_day"] == 18 and row["consolidated_until_day"] == 40


def test_world_quest_completion_feeds_faction_deed_only_with_faction():
    q = {**_quest(), "origin_faction_id": "legiao_ferro"}
    state = base_state()
    state["quests"] = [q]
    ev = {"type": "quest_completed", "payload": {"quest_id": q["id"]}, "target_id": q["id"]}
    info = reputation.deed_info(state, ev)
    assert info and info["faction_id"] == "legiao_ferro" and info["origin_npc"] == ""
    state["quests"] = [{**q, "origin_faction_id": ""}]
    assert reputation.deed_info(state, ev) is None  # sem fação: so XP e ouro


def test_shadow_logs_heard_offers_without_writing(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_QUESTS", "shadow")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    seen: list = []
    monkeypatch.setattr(wq, "_log", lambda action, **kw: seen.append(action))
    state = base_state()
    add_crisis(state)
    state["event_log"] = [
        {"event_id": "ev-1", "type": "location_state_changed", "payload": {"crisis_id": "crise-1"}}
    ]
    state["location_heard"] = {"brekmar": ["ev-1"]}
    quests, created = wq.offer_from_heard(state, 17)
    assert created == [] and quests == [] and "shadow_offer" in seen
