"""SPEC-240: correlação automática (request_id / action_ref / game_ref) em toda linha."""

import json
import threading
import uuid

import pytest

from observability import logging_setup
from observability.telemetry import (
    bind_correlation,
    contextualize,
    correlation_scope,
    log_event,
    pseudonym,
)


@pytest.fixture()
def client(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    from fastapi.testclient import TestClient

    return TestClient(api.app)


def _new_game(client) -> str:
    r = client.post(
        "/game/new",
        json={
            "name": "Streamer",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _stdout_lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def test_log_event_includes_request_id(capsys):
    logging_setup.configure_logging({})
    with correlation_scope(request_id="req-abc12345"):
        log_event("x", "inside")
    log_event("x", "outside")
    lines = {l["event"]: l for l in _stdout_lines(capsys)}
    assert lines["x.inside"]["request_id"] == "req-abc12345"
    assert "request_id" not in lines["x.outside"]


def test_explicit_field_wins_over_correlation(capsys):
    logging_setup.configure_logging({})
    with correlation_scope(request_id="from-scope-1"):
        log_event("x", "e", request_id="explicit-1")
    assert _stdout_lines(capsys)[-1]["request_id"] == "explicit-1"


def test_raw_action_id_never_logged(capsys):
    logging_setup.configure_logging({})
    action, game = str(uuid.uuid4()), str(uuid.uuid4())
    with correlation_scope(request_id="req-abc12345", game_id=game, action_id=action):
        log_event("x", "e")
    out = capsys.readouterr().out
    assert action not in out and game not in out
    assert json.loads(out)["action_ref"] == pseudonym(action)


def test_contextualize_carries_context_to_thread(capsys):
    logging_setup.configure_logging({})
    with correlation_scope(request_id="req-thread-1"):
        t = threading.Thread(target=contextualize(lambda: log_event("x", "in_thread")))
    t.start()
    t.join()
    assert _stdout_lines(capsys)[-1]["request_id"] == "req-thread-1"


def test_bind_correlation_sets_game_and_action():
    with correlation_scope(request_id="req-bind-001"):
        bind_correlation(game_id="g1", action_id="a1")
        from observability.telemetry import correlation

        c = correlation()
    assert c["game_ref"] == pseudonym("g1") and c["action_ref"] == pseudonym("a1")


def test_jev_shadow_line_has_action_ref(monkeypatch, capsys):
    from services import jev_rollout

    logging_setup.configure_logging({})
    seen = {}

    def fake_eval(*_a):
        from observability.telemetry import correlation

        seen.update(correlation())
        raise RuntimeError("stop")

    monkeypatch.setattr(jev_rollout, "_evaluate", fake_eval)
    with correlation_scope(request_id="req-jev-0001", action_id="a-jev"):
        fut = jev_rollout._pool().submit(contextualize(jev_rollout._evaluate), {}, "a", None, "k")
    try:
        fut.result(timeout=5)
    except RuntimeError:
        pass
    assert seen["request_id"] == "req-jev-0001" and seen["action_ref"] == pseudonym("a-jev")


def _turn_lines(lines, rid):
    return [
        l
        for l in lines
        if l.get("request_id") == rid and str(l.get("logger", "")).startswith("rpg.")
    ]


def test_turn_lines_share_action_ref(client, capsys):
    gid = _new_game(client)
    capsys.readouterr()
    action = str(uuid.uuid4())
    r = client.post(
        "/game/action",
        headers={"X-Request-ID": "test-req-0001"},
        json={"input_text": "olho ao redor", "game_id": gid, "action_id": action},
    )
    assert r.status_code == 200 and r.headers["X-Request-ID"] == "test-req-0001"
    lines = _turn_lines(_stdout_lines(capsys), "test-req-0001")
    assert len({l["event"] for l in lines}) >= 2, [l["event"] for l in lines]
    turn = next(l for l in lines if l["event"] == "turn")
    assert turn["action_ref"] == pseudonym(action) and turn["game_ref"] == pseudonym(gid)
    for l in lines:
        if "action_ref" in l:
            assert l["action_ref"] == pseudonym(action)


def test_sse_worker_lines_have_request_id(client, capsys):
    gid = _new_game(client)
    capsys.readouterr()
    action = str(uuid.uuid4())
    with client.stream(
        "POST",
        "/game/action/stream",
        headers={"X-Request-ID": "test-req-0002"},
        json={"input_text": "olho ao redor", "game_id": gid, "action_id": action},
    ) as r:
        for _ in r.iter_lines():
            pass
    out = capsys.readouterr().out
    assert action not in out and gid not in out
    lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    mine = _turn_lines(lines, "test-req-0002")
    turn = next(l for l in mine if l["event"] == "turn")
    assert turn["action_ref"] == pseudonym(action)
    assert len({l["event"] for l in mine}) >= 2, [l["event"] for l in mine]
