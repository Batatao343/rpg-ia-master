"""SPEC-228 — morte sem checkpoint, ordem save/checkpoint, flags e schema."""

import json
import os
import uuid
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

import api
import persistence
from services import checkpoints as cp
from tests.test_death_flow import _state


@pytest.fixture()
def client():
    api._rate_hits.clear()
    return TestClient(api.app)


def _idle(state):
    state["combat"] = {"active": False}
    state["enemies"] = []
    return state


def test_has_checkpoint_rejects_empty_file():
    gid = str(uuid.uuid4())
    os.makedirs(persistence.SAVES_DIR, exist_ok=True)
    path = persistence._safe_save_path(gid, suffix=".checkpoint")
    open(path, "w").close()
    assert persistence.has_checkpoint(gid) is False
    with open(path, "w") as f:
        json.dump({"foo": 1}, f)
    assert persistence.has_checkpoint(gid) is False


def test_has_checkpoint_accepts_valid():
    gid = str(uuid.uuid4())
    assert persistence.save_checkpoint(_idle(_state(gid, hp=30, gold=5)))
    assert persistence.has_checkpoint(gid) is True


def test_death_continue_without_checkpoint_refuses(client):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True, turn=30))
    r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
    assert r.status_code == 409
    body = r.json()
    assert body.get("code") == "no_restore_point"
    assert body.get("death_pending") is True
    reloaded = persistence.load_game_state(persistence.save_path(gid))
    assert reloaded["death_pending"] is True and reloaded["player"]["hp"] == 0


def test_death_continue_with_corrupt_checkpoint_refuses(client):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True, turn=30))
    with open(persistence._safe_save_path(gid, suffix=".checkpoint"), "w") as f:
        f.write("{broken")
    r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
    assert r.status_code == 409


def test_resolve_death_choice_strict_raises():
    st = _state(str(uuid.uuid4()), hp=0, gold=0, death_pending=True)
    with pytest.raises(cp.NoRestorePoint):
        cp.resolve_death_choice(st, "continue")
    ok = cp.resolve_death_choice(st, "continue", initial_state=_idle(_state("x", hp=30, gold=9)))
    assert ok["player"]["hp"] == 30
    assert cp.resolve_death_choice(st, "continue", strict=False)["death_pending"] is False


def test_synthetic_checkpoint_for_legacy_save():
    gid = str(uuid.uuid4())
    persistence.save_game_state(_idle(_state(gid, hp=20, gold=5, turn=12)))
    assert not persistence.has_checkpoint(gid)
    persistence.ensure_synthetic_checkpoint(persistence.load_game_state(persistence.save_path(gid)))
    assert persistence.has_checkpoint(gid)
    assert persistence.load_checkpoint(gid)["continuity"]["synthetic_from_turn"] == 12


def test_will_lose_turns_from_file(client):
    gid = str(uuid.uuid4())
    persistence.save_checkpoint(_idle(_state(gid, hp=30, gold=5, turn=10)))
    dead = _state(gid, hp=0, gold=0, death_pending=True, turn=25)
    dead["continuity"] = {"last_checkpoint_turn": 20}
    persistence.save_game_state(dead)
    ctx = api._death_block(persistence.load_game_state(persistence.save_path(gid)))
    assert ctx["will_restore_turn"] == 10
    assert ctx["will_lose_turns"] == 15


def test_needs_replan_roundtrip():
    gid = str(uuid.uuid4())
    st = _state(gid, hp=20, gold=1)
    st["needs_replan"] = True
    persistence.save_game_state(st)
    assert persistence.load_game_state(persistence.save_path(gid))["needs_replan"] is True
    st["needs_replan"] = False
    persistence.save_game_state(st)
    assert persistence.load_game_state(persistence.save_path(gid))["needs_replan"] is False


def test_newer_schema_refused(client):
    raw = {"schema_version": 99, "game_id": str(uuid.uuid4()), "player": {}}
    with pytest.raises(persistence.IncompatibleSaveError):
        persistence.migrate_state(raw)
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=20, gold=1))
    path = persistence.save_path(gid)
    data = json.load(open(path, encoding="utf-8"))
    data["schema_version"] = 99
    json.dump(data, open(path, "w", encoding="utf-8"))
    r = client.post("/game/action", json={"input_text": "x", "game_id": gid})
    assert r.status_code == 409
    assert json.load(open(path, encoding="utf-8"))["schema_version"] == 99


@pytest.mark.parametrize("version", [0, 3, 4, 5, 6, 7, 8])
def test_old_schemas_still_load(version):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=20, gold=1))
    path = persistence.save_path(gid)
    data = json.load(open(path, encoding="utf-8"))
    data["schema_version"] = version
    json.dump(data, open(path, "w", encoding="utf-8"))
    assert persistence.load_game_state(path) is not None


def test_commit_turn_defers_on_checkpoint_failure(monkeypatch):
    gid = str(uuid.uuid4())
    st = _idle(_state(gid, hp=20, gold=1, turn=10))
    st["continuity"] = {"last_checkpoint_turn": 0}
    monkeypatch.setattr(persistence, "save_checkpoint", lambda s: False)
    assert api._prepare_checkpoint(st, deepcopy(st)) is True
    assert st["continuity"]["last_checkpoint_turn"] == 0  # nao marcado antes de gravar
    api._commit_turn(
        st,
        api.format_response(st),
        claim=None,
        request_hash="",
        checkpoint=True,
        latency_ms=1,
        llm_events=[],
        llm_attempts=[],
    )
    saved = persistence.load_game_state(persistence.save_path(gid))
    assert saved["continuity"]["checkpoint_deferred"] is True
    assert saved["continuity"]["last_checkpoint_turn"] == 0
    st2 = deepcopy(saved)
    st2["world"]["turn_count"] = 11
    assert cp.should_checkpoint(st2) is True


def test_commit_turn_marks_after_checkpoint_success():
    gid = str(uuid.uuid4())
    st = _idle(_state(gid, hp=20, gold=1, turn=10))
    st["continuity"] = {"last_checkpoint_turn": 0, "checkpoint_deferred": True}
    assert api._prepare_checkpoint(st, deepcopy(st)) is True
    api._commit_turn(
        st,
        api.format_response(st),
        claim=None,
        request_hash="",
        checkpoint=True,
        latency_ms=1,
        llm_events=[],
        llm_attempts=[],
    )
    saved = persistence.load_game_state(persistence.save_path(gid))
    assert saved["continuity"]["last_checkpoint_turn"] == 10
    assert not saved["continuity"].get("checkpoint_deferred")
    assert persistence.checkpoint_turn(gid) == 10


def test_lock_latest_serializes_with_uuid():
    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=20, gold=1))
    assert api._game_lock(None) is api._game_lock(gid)


def test_stream_resolves_latest_once(client):
    gid = str(uuid.uuid4())
    persistence.save_game_state(_idle(_state(gid, hp=20, gold=1)))
    r = client.post("/game/action/stream", json={"input_text": "olho"})
    assert r.status_code == 200
    assert gid in r.text


def test_messages_roundtrip_all_types():
    msgs = [
        HumanMessage(content="oi", id="h1"),
        AIMessage(
            content="",
            tool_calls=[{"name": "f", "args": {"a": 1}, "id": "t1"}],
            additional_kwargs={"k": "v"},
            name="narrador",
        ),
        SystemMessage(content="sys"),
        ToolMessage(content="res", tool_call_id="t1"),
    ]
    back = persistence._deserialize_messages(persistence._serialize_messages(msgs))
    assert [type(m) for m in back] == [type(m) for m in msgs]
    assert back[1].tool_calls[0]["name"] == "f"
    assert back[1].additional_kwargs == {"k": "v"} and back[1].name == "narrador"
    assert isinstance(back[3], ToolMessage) and back[3].tool_call_id == "t1"
    legacy = [
        {"type": "human", "content": "a"},
        {"type": "ai", "content": "b"},
        {"type": "system", "content": "c"},
    ]
    assert [m.content for m in persistence._deserialize_messages(legacy)] == ["a", "b", "c"]


def test_crash_between_checkpoint_and_save_discards_ahead_checkpoint(client, monkeypatch):
    """§7: checkpoint gravado (t11) e crash antes do save (fica t10) → o slot à
    frente é descartado no próximo load de ação; a morte volta a um turno real."""
    gid = str(uuid.uuid4())
    base = _idle(_state(gid, hp=20, gold=5, turn=10))
    persistence.save_game_state(base)
    ahead = deepcopy(base)
    ahead["world"]["turn_count"] = 11
    ahead["player"]["gold"] = 999  # linha do tempo abortada
    ahead["continuity"] = {"last_checkpoint_turn": 0, "checkpoint_deferred": True}

    def _crash(_state, **_kw):
        raise RuntimeError("crash simulado após o checkpoint")

    with monkeypatch.context() as m:
        m.setattr(api, "_require_saved", _crash)
        m.setattr(api, "_schedule_chronicle_jobs", lambda *_a, **_k: None)
        with pytest.raises(RuntimeError):
            api._commit_turn(
                ahead,
                api.format_response(ahead),
                claim=None,
                request_hash="",
                checkpoint=True,
                latency_ms=1,
                llm_events=[],
                llm_attempts=[],
            )
    assert persistence.checkpoint_turn(gid) == 11  # slot à frente
    saved = persistence.load_game_state(persistence.save_path(gid))
    assert saved["world"]["turn_count"] == 10

    # mesma chamada que _execute_action faz antes do turno (perfil legacy)
    assert persistence.ensure_synthetic_checkpoint(saved) is True
    cp_state = persistence.load_checkpoint(gid)
    assert cp_state["world"]["turn_count"] == 10
    assert cp_state["continuity"]["synthetic_from_turn"] == 10
    assert cp_state["player"]["gold"] == 5
    # idempotente: checkpoint == save não é regravado
    assert persistence.ensure_synthetic_checkpoint(saved) is False

    dead = _state(gid, hp=0, gold=0, death_pending=True, turn=14)
    persistence.save_game_state(dead)
    ctx = api._death_block(persistence.load_game_state(persistence.save_path(gid)))
    assert ctx["will_restore_turn"] == 10 and ctx["will_lose_turns"] == 4
    r = client.post("/game/death", json={"game_id": gid, "choice": "continue"})
    assert r.status_code == 200
    restored = persistence.load_game_state(persistence.save_path(gid))
    assert restored["world"]["turn_count"] == 10
    assert restored["player"]["gold"] == 5 and restored["death_pending"] is False


def test_postgres_list_skips_newer_schema_rows(monkeypatch):
    """R9 (perfil DB): linha de schema mais novo não derruba a listagem."""
    from infrastructure import postgres as pg

    def _fake_stored(row):
        if row["schema_version"] > persistence.SCHEMA_VERSION:
            raise persistence.IncompatibleSaveError("v99")
        return row["id"]

    monkeypatch.setattr(pg, "_stored", _fake_stored)
    rows = [
        {"id": "nova", "schema_version": 99},
        {"id": "a", "schema_version": 8},
        {"id": "b", "schema_version": 8},
    ]
    assert pg._stored_rows_tolerant(rows) == ["a", "b"]

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, *_a, **_k):
            return self

        def fetchall(self):
            return rows

    class _Pool:
        def connection(self):
            return _Conn()

    store = pg.PostgresGameStore(_Pool())
    principal = type("P", (), {"user_id": "u"})()
    assert store.list(principal) == ["a", "b"]


def test_action_without_game_id_resolves_latest_once(client, monkeypatch):
    """R8: POST /game/action sem game_id resolve o "mais recente" UMA vez."""
    gid = str(uuid.uuid4())
    persistence.save_game_state(_idle(_state(gid, hp=20, gold=1)))
    real = persistence.get_latest_save_file
    calls = []

    def _counting():
        calls.append(1)
        return real()

    monkeypatch.setattr(persistence, "get_latest_save_file", _counting)
    seen = []
    orig_lock = api._game_lock
    monkeypatch.setattr(api, "_game_lock", lambda g: seen.append(g) or orig_lock(g))
    r = client.post("/game/action", json={"input_text": "olho ao redor"})
    assert r.status_code == 200, r.text
    assert len(calls) == 1
    assert seen == [gid]
    assert r.json()["game_id"] == gid


def test_cli_persist_turn_checkpoint_before_save(monkeypatch):
    """R5 (CLI): checkpoint antes do save; falha adia sem marcar."""
    import game_engine

    order = []
    gid = str(uuid.uuid4())
    st = _idle(_state(gid, hp=20, gold=1, turn=10))
    st["continuity"] = {"last_checkpoint_turn": 0}
    real_cp, real_save = persistence.save_checkpoint, game_engine.save_game_state
    monkeypatch.setattr(
        persistence, "save_checkpoint", lambda s: order.append("checkpoint") or real_cp(s)
    )
    monkeypatch.setattr(
        game_engine, "save_game_state", lambda s: order.append("save") or real_save(s)
    )
    st = game_engine._persist_turn_cli(st)
    assert order == ["checkpoint", "save"]
    assert st["continuity"]["last_checkpoint_turn"] == 10
    assert persistence.checkpoint_turn(gid) == 10

    st2 = _idle(_state(str(uuid.uuid4()), hp=20, gold=1, turn=20))
    st2["continuity"] = {"last_checkpoint_turn": 10}
    monkeypatch.setattr(persistence, "save_checkpoint", lambda s: False)
    st2 = game_engine._persist_turn_cli(st2)
    saved = persistence.load_game_state(persistence.save_path(st2["game_id"]))
    assert saved["continuity"]["last_checkpoint_turn"] == 10
    assert saved["continuity"]["checkpoint_deferred"] is True


def test_cli_resumed_death_pending_opens_death_flow(monkeypatch):
    """CLI: save retomado já caído abre a tela de morte antes de jogar."""
    import game_engine

    gid = str(uuid.uuid4())
    persistence.save_game_state(_state(gid, hp=0, gold=0, death_pending=True, turn=7))
    answers = iter(["1", "n"])  # Continuar → sem retorno → não aceita
    monkeypatch.setattr("builtins.input", lambda *_a: next(answers))
    monkeypatch.setattr(game_engine, "clear_screen", lambda: None)
    monkeypatch.setattr(
        game_engine,
        "load_game_state",
        lambda *_a: persistence.load_game_state(persistence.save_path(gid)),
    )
    monkeypatch.setattr(game_engine, "app", None)  # nunca chega ao grafo
    game_engine.run_game_loop()
    saved = persistence.load_game_state(persistence.save_path(gid))
    assert saved["death_pending"] is True and not saved.get("game_over")

    answers2 = iter(["2"])  # Aceitar o fim → memorial
    monkeypatch.setattr("builtins.input", lambda *_a: next(answers2))
    game_engine.run_game_loop()
    assert persistence.load_game_state(persistence.save_path(gid))["game_over"] is True
