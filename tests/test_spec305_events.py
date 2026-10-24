"""SPEC-305 Etapa 1: quest_failed engine-only, derivado de alivio, saves antigos."""

from __future__ import annotations

import json

from services import quest_log as ql
from services.event_processor import process_pending_events
from services.world_validators import reason_code, validate_proposal


def _state(**over) -> dict:
    base = {
        "game_id": "g-305",
        "world": {"turn_count": 5, "world_clock": {"day": 9, "period": "Manhã"}},
        "world_projection": {},
        "event_log": [],
        "pending_world_events": [],
        "chronicle": [],
        "quests": [],
    }
    base.update(over)
    return base


def _quest(**over) -> dict:
    q = {
        "id": "q1",
        "title": "Conter a febre em Brekmar",
        "status": "active",
        "created_turn": 1,
        "resolved_turn": 0,
        "location_id": "brekmar",
        "progress_log": [],
        "fail_text": "O prazo para conter a febre em Brekmar se esgotou.",
    }
    q.update(over)
    return q


def test_quest_failed_llm_proposal_rejected():
    state = _state(quests=[_quest()])
    prop = {"type": "quest_failed", "target_id": "q1", "payload": {"quest_id": "q1"}}
    res = validate_proposal(prop, state)
    assert not res.ok and reason_code(res.reason) == "engine_only"
    assert not validate_proposal({**prop, "source": "storyteller"}, state).ok


def test_quest_failed_engine_marks_failed_and_milestone():
    ev = {
        "type": "quest_failed",
        "actor_id": "engine",
        "target_id": "q1",
        "payload": {"quest_id": "q1", "reason": "prazo", "quest_title": "x"},
        "source": "engine",
    }
    out = process_pending_events(_state(quests=[_quest()], pending_world_events=[ev, dict(ev)]))
    q = out["quests"][0]
    assert q["status"] == "failed" and q["fail_reason"] == "prazo" and q["resolved_day"] == 9
    assert "se esgotou" in q["description"]
    # a segunda falha da mesma quest e rejeitada (uma falha por quest)
    assert len([e for e in out["event_log"] if e["type"] == "quest_failed"]) == 1
    assert any("fracassou" in e["text"] for e in out["chronicle"][-1]["entries"])


def test_fail_orphan_path_unchanged():
    quests, events = ql.fail_orphan_quests([_quest(origin_entity_id="npc_x")], "npc_x", 4)
    assert quests[0]["status"] == "failed"
    assert events[0]["source"] == "system" and events[0]["payload"]["reason"] == "origin_killed"


def test_world_quest_relief_only_as_derived():
    prop = {
        "type": "world_quest_relief",
        "target_id": "brekmar",
        "payload": {},
        "source": "engine",
    }
    assert not validate_proposal(prop, _state()).ok


def test_relief_derived_on_completion_of_world_quest():
    q = _quest(world_kind="conter_praga", world_source_id="c1", region_id="brekmar")
    ev = {
        "type": "quest_completed",
        "target_id": "q1",
        "payload": {"quest_id": "q1"},
        "source": "engine",
    }
    out = process_pending_events(_state(quests=[q], pending_world_events=[ev]))
    rel = [e for e in out["event_log"] if e["type"] == "world_quest_relief"]
    assert len(rel) == 1
    p = rel[0]["payload"]
    assert p["pressure"] == "praga" and p["delta"] < 0 and p["world_source_id"] == "c1"
    assert out["quests"][0]["status"] == "completed"


def test_expire_quest_is_pure_and_idempotent():
    qs = [_quest()]
    out = ql.expire_quest(qs, "q1", 3, 8)
    assert qs[0]["status"] == "active" and out[0]["status"] == "expired"
    assert ql.expire_quest(out, "q1", 4, 9) == out


def test_legacy_quest_without_world_fields_roundtrip(tmp_path, monkeypatch):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    legacy = {"id": "old", "title": "Antiga", "status": "active", "location_id": ""}
    save = {
        "game_id": "velho",
        "player": {"inventory": []},
        "world": {},
        "quests": [legacy],
        "messages": [{"type": "ai", "content": "Oi."}],
    }
    (tmp_path / "velho.json").write_text(json.dumps(save), encoding="utf-8")
    state = persistence.load_game_state(str(tmp_path / "velho.json"))
    assert state["quests"][0]["title"] == "Antiga"
    view = ql.public_quest_view(state["quests"][0], 5)
    assert view["kind"] == "comum" and "deadline_label" not in view
