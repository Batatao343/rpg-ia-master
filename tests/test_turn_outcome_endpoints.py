"""SPEC-199 - origem do ganho (source) e endpoints (SSE/POST replay)."""

from __future__ import annotations

import re
import uuid
from copy import deepcopy

from langchain_core.messages import AIMessage

from services import turn_outcome as to

LEAK = re.compile(r"\+\d+\s*XP|\[RESULTADO\]")


def _src(origin, amount=100, kind="xp"):
    bl = to.record_gain(
        {"turn": 1, "xp": 0, "gold": 0, "level": 1, "inventory": {}}, kind, amount, origin
    )
    state = {
        "game_id": "g",
        "world": {"turn_count": 1},
        "player": {
            "xp": amount if kind == "xp" else 0,
            "gold": amount if kind == "gold" else 0,
            "level": 1,
            "inventory": [],
        },
        "turn_baseline": bl,
        "messages": [AIMessage(content="ok")],
    }
    return to.finalize_outcome(state)["source"]


def test_source_from_recorded_origins():
    assert _src("beat") == "story"
    assert _src("quest") == "quest"
    assert _src("combat") == "combat"
    assert _src("loot", 5, "gold") == "loot"
    assert _src("exploration", 5, "gold") == "exploration"


def test_source_mixed_when_origins_differ():
    bl = {"turn": 1, "xp": 0, "gold": 0, "level": 1, "inventory": {}}
    bl = to.record_gain(bl, "xp", 100, "beat")
    bl = to.record_gain(bl, "gold", 20, "quest")
    assert bl["gain_origins"] == ["beat", "quest"]
    state = {
        "game_id": "g",
        "world": {"turn_count": 1},
        "player": {"xp": 100, "gold": 20, "level": 1, "inventory": []},
        "turn_baseline": bl,
        "messages": [AIMessage(content="ok")],
    }
    assert to.finalize_outcome(state)["source"] == "mixed"


def test_sse_state_carries_turn_outcome_equal_to_get_state(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import api
    import persistence
    from tests.test_streaming import _new_game, _read_sse

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    client = TestClient(api.app)
    gid = _new_game(client)
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": "olho ao redor", "game_id": gid}
    ) as r:
        events = _read_sse(r)
    state_evt = next(d for e, d in events if e == "state")
    assert "turn_outcome" in state_evt
    got = client.get("/game/state", params={"game_id": gid}).json()
    assert got["turn_outcome"] == state_evt["turn_outcome"]
    narr = "".join(d["chunk"] for e, d in events if e == "narrative")
    assert not LEAK.search(narr)


def test_post_replay_same_receipt_single_xp_grant(monkeypatch):
    from fastapi.testclient import TestClient

    import api
    import persistence
    from tests.test_hardening_persistencia_sse import _state

    gid = str(uuid.uuid4())
    base = _state(gid)
    base["player"].setdefault("xp", 0)
    assert persistence.save_game_state(base)
    calls = []

    class Graph:
        def invoke(self, current):
            calls.append(1)
            out = deepcopy(current)
            out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
            out["player"]["xp"] = int(out["player"].get("xp", 0)) + 50
            out["last_turn_outcome"] = {
                "receipt_id": "rc-1",
                "turn": 1,
                "xp_delta": 50,
                "player_message": "O rato tomba.\n\n[RESULTADO] +50 XP",
            }
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="O rato tomba.")]
            return out

    monkeypatch.setattr(api, "game_graph", Graph())
    client = TestClient(api.app)
    body = {"game_id": gid, "input_text": "ataco", "action_id": str(uuid.uuid4())}
    first = client.post("/game/action", json=body)
    second = client.post("/game/action", json=body)
    assert len(calls) == 1
    assert first.json()["turn_outcome"] == second.json()["turn_outcome"]
    assert second.json()["turn_outcome"]["receipt_id"] == "rc-1"
    assert second.json()["player_stats"]["xp"] == base["player"]["xp"] + 50
    assert not LEAK.search(second.json()["message"])
