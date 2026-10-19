"""SPEC-215 R8 — o ledger de conhecimento NUNCA sai pela API pública."""

from __future__ import annotations

import json

from services import npc_layers
from services.discovery import player_codex

PRIVATE_KEYS = ("knowledge_links", "knowledge_queue", "location_heard", "legacy_knowledge")


def _state_with_ledger() -> dict:
    import persistence

    with open("tests/fixtures/save_v8_pre_spec202.json", encoding="utf-8") as fh:
        state = persistence._raw_to_state(json.load(fh))
    state["knowledge_links"] = [
        {
            "link_id": "secretlink",
            "holder_id": "npc:npc_mv_brunna_ponte_alta",
            "subject_kind": "event",
            "subject_id": "ev_sigiloso",
            "relation": "observed_by",
            "source": "world",
            "channel": "witness",
            "hops": 0,
            "acquired_clock": 3,
            "acquired_turn": 2,
        }
    ]
    state["knowledge_queue"] = [
        {
            "delivery_id": "dsig",
            "subject_kind": "event",
            "subject_id": "ev_sigiloso",
            "from_location_id": "brekmar",
            "to_location_id": "ophidia",
            "hop": 1,
            "due_clock": 9,
            "created_turn": 2,
        }
    ]
    state["location_heard"] = {"brekmar": ["ev_sigiloso"]}
    return state


def _assert_private(payload) -> None:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    for key in (*PRIVATE_KEYS, "secretlink", "dsig", "ev_sigiloso"):
        assert key not in text, key


def test_game_state_response_has_no_knowledge():
    import api

    resp = api.format_response(_state_with_ledger())
    _assert_private(resp.model_dump() if hasattr(resp, "model_dump") else resp)


def test_codex_has_no_knowledge():
    _assert_private(player_codex(_state_with_ledger()))


def test_visible_npc_view_has_no_knowledge():
    state = _state_with_ledger()
    _assert_private(npc_layers.visible_npc_view(state.get("npcs") or {}))
