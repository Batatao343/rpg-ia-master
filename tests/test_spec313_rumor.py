"""SPEC-313 Etapa 5: investigar_rumor (boato falso tambem gera quest; verdade so na conclusao)."""

from __future__ import annotations

import json

import pytest

from services import event_processor as ep
from services import lore_quests as lq
from services import quest_log
from services import world_quests as wq
from tests.spec313_helpers import add_rumor, npc_state, setup_env

DAY = 17


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    setup_env(monkeypatch)


def _state(truth=True, perceived=15):
    st = npc_state(loc="nova_arcadia")
    st["npcs"] = {}
    rid = add_rumor(st, truth=truth, perceived=perceived)
    st["player"] = {"name": "H", "level": 1, "xp": 0, "gold": 10, "inventory": []}
    return st, rid


def _offered(st):
    quests, created = wq.offer_from_heard(st, DAY)
    assert len(created) == 1
    st["quests"] = quests
    return created[0]


def _complete(st, quest, turn=20):
    st["world"] = {**st["world"], "turn_count": turn}
    ev = {
        "type": "quest_completed",
        "actor_id": "player",
        "target_id": quest["id"],
        "detail": "",
        "payload": {"quest_id": quest["id"]},
        "source": "system",
    }
    return ep.process_pending_events({**st, "pending_world_events": [ev]})


def test_heard_rumor_with_hook_creates_quest_engine_origin():
    st, rid = _state()
    q = _offered(st)
    assert q["world_kind"] == "investigar_rumor" and q["lore_origin_key"] == "engine"
    assert q["heard_via"]["channel"] == "rumor" and q["heard_via"]["event_id"] == rid
    assert q["reward_gold_planned"] == 0 and q["reward_hint"] == ""
    assert q["location_id"] == "na_anel_ferro" and "Alguém precisa ir até" in q["description"]


def test_unheard_rumor_creates_nothing():
    st, _rid = _state(perceived=0)
    assert wq.offer_from_heard(st, DAY)[1] == []


def test_false_rumor_quest_payload_equals_true_rumor_payload_while_active():
    a, _ = _state(truth=True)
    b, _ = _state(truth=False)
    qa, qb = _offered(a), _offered(b)
    assert qa == qb
    day = DAY
    assert quest_log.public_quest_view(qa, day) == quest_log.public_quest_view(qb, day)
    blob = json.dumps(quest_log.public_quest_view(qa, day), ensure_ascii=False)
    assert "truth" not in blob and "outcome" not in blob and qa["lore_anchor"]["id"] not in blob


def test_false_rumor_completes_desmentido_and_no_fact():
    st, rid = _state(truth=False)
    q = _offered(st)
    out = _complete(st, q)
    done = out["quests"][0]
    assert done["status"] == "completed" and done["outcome"] == "desmentido"
    assert out["world_sim"]["rumors"][0]["resolution"] == "desmentido"
    log_blob = json.dumps(out["event_log"], ensure_ascii=False)
    assert rid not in log_blob and "Legião" not in log_blob and q["title"] not in log_blob
    view = quest_log.public_quest_view(done, DAY)
    assert view["outcome_label"] == "era só boato"


def test_true_rumor_completes_confirmado():
    st, _rid = _state(truth=True)
    q = _offered(st)
    out = _complete(st, q)
    assert out["quests"][0]["outcome"] == "confirmado"
    assert out["world_sim"]["rumors"][0]["resolution"] == "confirmado"
    assert quest_log.public_quest_view(out["quests"][0], DAY)["outcome_label"] == "confirmado"


def test_outcome_hook_is_clean_for_other_investigations():
    st, _rid = _state(truth=False)
    q = _offered(st)
    outcome, sim = lq.resolve_rumor_outcome(st, q, DAY)
    assert outcome == "desmentido" and sim["rumors"][0]["resolution"] == "desmentido"
    gone = lq.resolve_rumor_outcome({**st, "world_sim": {"rumors": []}}, q, DAY)[0]
    assert gone == "inconclusivo"


def test_desfecho_line_next_turn_only_after_completion():
    st, _rid = _state(truth=False)
    q = _offered(st)
    assert lq.desfecho_block(st) == ""
    out = _complete(st, q, turn=20)
    after = {**st, **out, "world": {**st["world"], "turn_count": 21}}
    block = lq.desfecho_block(after)
    assert "boato" in block and "<DESFECHO_DE_QUEST>" in block
    later = {**after, "world": {**st["world"], "turn_count": 40}}
    assert lq.desfecho_block(later) == ""


def test_rumor_kind_disabled_without_312(monkeypatch):
    st, _rid = _state()
    monkeypatch.setattr(wq, "_rumor_api", lambda: None)
    assert not [s for s in wq.candidates(st, DAY) if s.kind == "investigar_rumor"]
    assert wq.offer_from_heard(st, DAY)[1] == []
    npc = npc_state(loc="nova_arcadia")
    assert not [i for i in lq.anchor_menu(npc, "Rolf")[1] if i["kind"] == "investigar_rumor"]


def test_rumor_quest_never_becomes_fact_invariant():
    from playtest import invariants

    st, _rid = _state(truth=False)
    q = _offered(st)
    out = _complete(st, q)
    final = {**st, **out}
    assert not [
        v for v in invariants.check_rumors(final, None, 21) if v.check_id == "rumor.became_fact"
    ]
    assert not [v for v in invariants.check_world_quests(final, None, 21)]
