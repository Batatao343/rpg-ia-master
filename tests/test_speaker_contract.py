"""SPEC-202 Etapa 4 — `speaker` canônico em POST/SSE/state/history + saves."""

from __future__ import annotations

import json
import os
from copy import deepcopy

import pytest
from langchain_core.messages import HumanMessage

import persistence
from services import interlocutor as itl

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "save_v8_pre_spec202.json")
BRUNNA = {
    "kind": "npc",
    "id": "npc_mv_brunna_ponte_alta",
    "name": "Brunna Ponte-Alta",
    "reason": "direct_address",
}


@pytest.fixture()
def client(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    from fastapi.testclient import TestClient

    return TestClient(api.app)


def _new_game_with_brunna(client) -> str:
    r = client.post(
        "/game/new",
        json={
            "name": "Falante",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    gid = r.json()["game_id"]
    state = persistence.load_game_state(persistence.save_path(gid))
    loc_id = state["world"].get("current_location_id", "")
    state["npcs"] = {
        "Brunna Ponte-Alta": {
            "name": "Brunna Ponte-Alta",
            "role": "Barqueira",
            "in_scene": True,
            "home_location_id": loc_id,
            "relationship": 5,
            "memory": [],
            "known_by_player": True,
        }
    }
    assert persistence.save_game_state(state)
    return gid


def _read_sse(resp) -> list:
    events, name = [], None
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("event: "):
            name = line[len("event: ") :].strip()
        elif line.startswith("data: ") and name:
            events.append((name, json.loads(line[len("data: ") :])))
            name = None
    return events


def test_speaker_em_post_e_sse_identicos(client):
    text = "Brunna, você viu o barco?"
    gid_post = _new_game_with_brunna(client)
    post = client.post("/game/action", json={"input_text": text, "game_id": gid_post})
    assert post.status_code == 200, post.text
    assert post.json()["speaker"] == BRUNNA

    gid_sse = _new_game_with_brunna(client)
    with client.stream(
        "POST", "/game/action/stream", json={"input_text": text, "game_id": gid_sse}
    ) as resp:
        events = _read_sse(resp)
    final = next(d for e, d in events if e == "state")
    assert final["speaker"] == BRUNNA

    for gid in (gid_post, gid_sse):
        state = client.get("/game/state", params={"game_id": gid}).json()
        assert state["speaker"] == BRUNNA
        history = client.get("/game/history", params={"game_id": gid}).json()["entries"]
        last = [row for row in history if row["role"] == "narrator"][-1]
        assert (last["speaker_kind"], last["speaker_id"], last["speaker_name"]) == (
            "npc",
            BRUNNA["id"],
            BRUNNA["name"],
        )


def test_meta_turno_api_speaker_narrador(client):
    gid = _new_game_with_brunna(client)
    r = client.post(
        "/game/action",
        json={"input_text": "Pergunto ao narrador o que a Brunna sente", "game_id": gid},
    )
    assert r.status_code == 200, r.text
    assert r.json()["speaker"] == {
        "kind": "narrator",
        "id": "narrator",
        "name": "Narrador",
        "reason": "meta_to_narrator",
    }
    assert not r.json()["message"].startswith("**Brunna")


def test_speaker_id_estavel_entre_aliases():
    base = {
        "world": {"turn_count": 3, "current_location_id": "brekmar"},
        "npcs": {
            "Brunna Ponte-Alta": {
                "name": "Brunna Ponte-Alta",
                "in_scene": True,
                "home_location_id": "brekmar",
            }
        },
        "party": [],
        "next": "npc_actor",
    }
    ids = set()
    for ref in ("Brunna Ponte-Alta", "brunna ponte alta", "npc_brunna_ponte_alta"):
        sp = itl.speaker_for_turn(
            {**base, "active_npc_name": ref, "interlocutor_reason": "direct_address"}
        )
        ids.add((sp["id"], sp["name"]))
    assert ids == {("npc_mv_brunna_ponte_alta", "Brunna Ponte-Alta")}


def test_speaker_round_trip_save_load(tmp_path):
    state = persistence.migrate_state(json.load(open(FIXTURE, encoding="utf-8")))
    state = persistence.load_game_state(_write(tmp_path, state))
    speaker = {**BRUNNA, "turn": 4, "state_key": "Brunna Ponte-Alta"}
    state["last_speaker"] = deepcopy(speaker)
    path = persistence.save_path(state["game_id"])
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(path)
    assert loaded["last_speaker"] == speaker
    assert itl.response_speaker(loaded) == BRUNNA


def _write(tmp_path, raw: dict) -> str:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_history_legado_sem_speaker_carrega(tmp_path):
    raw = json.load(open(FIXTURE, encoding="utf-8"))
    assert raw["schema_version"] == 8
    assert "last_speaker" not in raw
    rows = [r for r in raw["presentation_history"] if r["role"] == "narrator"]
    assert rows and all("speaker_kind" not in r for r in rows)

    state = persistence.load_game_state(_write(tmp_path, raw))
    assert state is not None
    assert itl.response_speaker(state)["kind"] == "narrator"
    from services.presentation_history import history_page

    page = history_page(state)
    for row in page["entries"]:
        if row["role"] == "narrator":
            expected = "npc" if row["type"] == "NPC" else "narrator"
            assert row["speaker_kind"] == expected

    # Aditivo (sem bump): v8 segue v8; migrate é no-op idempotente.
    migrated = persistence.migrate_state(raw)
    assert migrated["schema_version"] == persistence.SCHEMA_VERSION == 8
    assert persistence.migrate_state(deepcopy(migrated)) == migrated
    assert state["last_speaker"] == {}

    # Round-trip: save do estado carregado → reload preserva/defaulta idêntico.
    assert persistence.save_game_state(state)
    on_disk = json.load(open(persistence.save_path(state["game_id"]), encoding="utf-8"))
    assert on_disk["schema_version"] == 8 and on_disk["last_speaker"] == {}
    again = persistence.load_game_state(persistence.save_path(state["game_id"]))
    assert again["last_speaker"] == {}
    assert itl.response_speaker(again)["kind"] == "narrator"


def test_load_v8_npc_legado_sem_id_e_last_speaker_invalido(tmp_path):
    raw = {
        "schema_version": 8,
        "game_id": "00000000-0000-0000-0000-000000000202",
        "last_speaker": "lixo",
        "presentation_history": [
            {"id": "a", "role": "narrator", "type": "NPC", "text": "**X:** oi"},
            {"id": "b", "role": "player", "type": "STORY", "text": "oi"},
        ],
    }
    assert persistence.migrate_state(deepcopy(raw)) == raw  # sem migração nova
    state = persistence.load_game_state(_write(tmp_path, raw))
    assert state["last_speaker"] == {}
    assert itl.response_speaker(state)["kind"] == "narrator"
    from services.presentation_history import history_page

    rows = history_page(state)["entries"]
    npc = next(r for r in rows if r["id"] == "a")
    assert npc["speaker_kind"] == "npc" and npc["speaker_id"] == ""
    assert "speaker_kind" not in next(r for r in rows if r["id"] == "b")


def test_recusa_de_acao_speaker_system(monkeypatch):
    import agents.action_guard as guard

    monkeypatch.setattr(guard, "orphan_transition", lambda _s: None)
    monkeypatch.setattr(
        guard,
        "evaluate_action",
        lambda _s, _a: {
            "phase": "unconscious",
            "allowed": False,
            "code": "blocked_unconscious",
            "action_kind": "none",
            "message": "Você está inconsciente.",
        },
    )
    previous = {**BRUNNA, "turn": 2, "state_key": "Brunna Ponte-Alta"}
    state = {
        "messages": [HumanMessage(content="Ataco o dragão")],
        "world": {"turn_count": 2},
        "last_speaker": previous,
    }
    out = guard.action_guard_node(state)
    assert out["action_guard_blocked"] is True
    assert out["last_speaker"]["kind"] == "system"
    assert out["last_speaker"]["last_npc"]["state_key"] == "Brunna Ponte-Alta"
    merged = {**state, **out}
    assert itl.response_speaker(merged) == {
        "kind": "system",
        "id": "system",
        "name": "Sistema",
        "reason": "action_refused",
    }
