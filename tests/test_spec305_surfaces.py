"""SPEC-305 Etapa 6: API com lista branca, rotulos de prazo, prompt e relatorio."""

from __future__ import annotations

import json

import pytest

from agents.storyteller import _gancho_novo_block, _quests_ativas_block
from services import quest_log as ql
from services import world_quests as wq
from tests.spec305_helpers import add_crisis, base_state, crisis_item

INTERNAL = (
    "deadline_day",
    "world_source_id",
    "heard_via",
    "origin_faction_id",
    "fail_reason",
    "world_kind",
)


def _world_quest(**over) -> dict:
    state = base_state()
    add_crisis(state)
    _q, created = wq.offer_from_perceived(state, [crisis_item()], 17)
    return {**created[0], **over}


def test_api_quest_view_whitelist():
    import api

    q = _world_quest(fail_reason="prazo")
    block = api._quest_block({}, [q], {"world_clock": {"day": 16}})
    side = block["side"][0]
    assert side["kind"] == "mundo" and side["deadline_label"] == "há algum tempo"
    blob = json.dumps(block)
    for key in INTERNAL:
        assert key not in side and f'"{key}"' not in blob
    assert "crise-1" not in blob


@pytest.mark.parametrize(
    "left,label",
    [
        (0, "urgente"),
        (2, "urgente"),
        (3, "em poucos dias"),
        (5, "em poucos dias"),
        (6, "há algum tempo"),
    ],
)
def test_deadline_label_buckets(left, label):
    assert ql.deadline_label(left) == label


def test_failed_and_expired_same_public_label():
    for status in ("failed", "expired"):
        view = ql.public_quest_view(_world_quest(status=status), 30)
        assert view["deadline_label"] == "prazo esgotado"


def test_prompt_block_has_deadline_label_no_number():
    q = _world_quest()
    text = _quests_ativas_block([q], {"world": {"world_clock": {"day": 16}}, "quests": [q]})
    assert "tipo: mundo" in text and "prazo: há algum tempo" in text
    assert str(q["deadline_day"]) not in text.replace(q["id"], "")


def test_gancho_novo_line_has_channel_no_deadline():
    q = _world_quest()
    block = _gancho_novo_block([q])
    assert "<GANCHO_NOVO>" in block and "testemunho" in block
    assert _gancho_novo_block([]) == ""


def test_report_world_quest_summary():
    from playtest import telemetry

    q = _world_quest(status="failed")
    summary = telemetry._world_summary({"world_sim": {"crises": []}, "quests": [q]})
    assert summary["world_quests"]["failed"] == 1
    assert summary["world_quests"]["by_channel"] == {"testemunho": 1}
