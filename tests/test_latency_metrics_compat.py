"""SPEC-200 Etapas 2/3 — metricas, compatibilidade e linha `rpg.turn` aditiva."""
from __future__ import annotations

import json
import logging
import random
import shutil
import subprocess
import threading
import uuid
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import api
import persistence
from llm_setup import LLMAttemptEvent, ModelTier, _emit_attempt_telemetry
from observability import latency as lat
from observability.latency import FakeClock
from observability.metrics import LABELS, metrics

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _new_game(client) -> str:
    r = client.post("/game/new", json={
        "name": "Lat", "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": ""})
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


def _sse(resp) -> list:
    events, name = [], None
    for line in resp.iter_lines():
        line = line.decode() if isinstance(line, bytes) else line
        if line.startswith("event: "):
            name = line[7:].strip()
        elif line.startswith("data: ") and name:
            events.append((name, json.loads(line[6:])))
            name = None
    return events


def _snap(prefix: str) -> dict:
    return {k: v for k, v in metrics.snapshot().items() if k.startswith(prefix)}


def _attempt(tier=ModelTier.FAST, *, outcome="success", usage=None, fell_back=False,
             provider="deepseek", latency_ms=10, index=0):
    return LLMAttemptEvent(
        provider=provider, model="m", tier=tier, attempt_index=index,
        latency_ms=latency_ms, fell_back=fell_back, outcome=outcome, error=None,
        structured=False, usage=usage)


class _Graph:
    """Grafo falso: um no, tentativas LLM controladas, nenhuma rede."""

    def __init__(self, attempts=(), advance=None):
        self.attempts, self.advance = list(attempts), advance

    def stream(self, current, **_kwargs):
        yield "updates", {"campaign_manager": {}}
        for event in self.attempts:
            _emit_attempt_telemetry(event)
        if self.advance:
            self.advance()
        out = deepcopy(current)
        out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
        out["messages"] = list(out.get("messages") or []) + [AIMessage(content="Texto do narrador.")]
        yield "updates", {"archivist": {}}
        yield "values", out


def _state(gid: str) -> dict:
    req = api.CombatSimulatorRequest(
        class_name=next(iter(api.gamedata.CLASSES)), level=1,
        enemy_id=next(iter(api.gamedata.BESTIARY)), quantity=1)
    state = api._build_combat_simulator_state(req)
    state["game_id"] = gid
    state["combat_simulation"] = {"enabled": False}
    state["combat"] = {"active": False, "round": 0, "scene": None}
    state["enemies"] = []
    return state


def _turn_lines(caplog) -> list:
    return [json.loads(r.getMessage()) for r in caplog.records
            if r.name == "rpg.turn" and '"evt": "turn"' in r.getMessage().replace('":"', '": "')]


def _run_post_turn(monkeypatch, caplog, graph, text="avanço", gid=None):
    gid = gid or str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))
    monkeypatch.setattr(api, "game_graph", graph)
    caplog.set_level(logging.INFO, logger="rpg.turn")
    with TestClient(api.app) as c:
        r = c.post("/game/action", json={"game_id": gid, "input_text": text,
                                          "action_id": str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    return [json.loads(rec.getMessage()) for rec in caplog.records
            if rec.name == "rpg.turn" and json.loads(rec.getMessage()).get("evt") == "turn"]


# --- compat de metricas ------------------------------------------------------

def test_old_sse_metric_still_registered_and_observed(client):
    assert "rpg_sse_first_event_seconds" in LABELS
    gid = _new_game(client)
    before = _snap("rpg_sse_first_event_seconds").get(
        "rpg_sse_first_event_seconds{'route': '/game/action/stream'}.count", 0)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "olho ao redor", "game_id": gid}) as r:
        _sse(r)
    after = _snap("rpg_sse_first_event_seconds")[
        "rpg_sse_first_event_seconds{'route': '/game/action/stream'}.count"]
    assert after == before + 1


def test_ack_metric_measures_after_yield(client, monkeypatch):
    """Atraso ANTES do primeiro byte aparece no ack honesto, nao na metrica antiga."""
    gid = _new_game(client)
    clock = FakeClock()
    lat.set_clock(clock)
    real_load = api.load_game_state

    def slow_load(*args, **kwargs):
        clock.advance(1.5)             # atraso injetado no handler, antes do stream
        return real_load(*args, **kwargs)

    monkeypatch.setattr(api, "load_game_state", slow_load)
    ack_key = "rpg_sse_ack_seconds{'route': '/game/action/stream'}"
    old_key = "rpg_sse_first_event_seconds{'route': '/game/action/stream'}"
    ack_before = _snap("rpg_sse_ack_seconds").get(ack_key + ".sum", 0.0)
    old_before = _snap("rpg_sse_first_event_seconds").get(old_key + ".sum", 0.0)
    try:
        with client.stream("POST", "/game/action/stream",
                           json={"input_text": "olho", "game_id": gid}) as r:
            _sse(r)
    finally:
        lat.set_clock(None)
    ack_delta = _snap("rpg_sse_ack_seconds")[ack_key + ".sum"] - ack_before
    old_delta = _snap("rpg_sse_first_event_seconds")[old_key + ".sum"] - old_before
    assert ack_delta >= 1.5
    assert old_delta < 0.5


def test_labels_closed_for_new_metrics():
    for name in ("rpg_sse_ack_seconds", "rpg_turn_phase_seconds",
                 "rpg_turn_first_content_seconds", "rpg_turn_last_content_seconds"):
        assert name in LABELS
    with pytest.raises(ValueError):
        metrics.observe("rpg_sse_ack_seconds", {"route": "/x", "game_id": "g"}, 1.0)
    with pytest.raises(ValueError):
        metrics.observe("rpg_turn_phase_seconds", {"route": "/x"}, 1.0)
    assert LABELS["rpg_turn_first_content_seconds"] == {"route", "source"}


def test_turn_duration_route_stream(client):
    gid = _new_game(client)
    key = "rpg_turn_duration_seconds{'outcome': 'ok', 'route': '/game/action/stream', 'simulated': 'true'}.count"
    before = _snap("rpg_turn_duration_seconds").get(key, 0)
    with client.stream("POST", "/game/action/stream",
                       json={"input_text": "olho", "game_id": gid}) as r:
        _sse(r)
    assert _snap("rpg_turn_duration_seconds")[key] == before + 1
    r = client.post("/game/action", json={"input_text": "olho", "game_id": gid})
    assert r.status_code == 200
    post_key = key.replace("/game/action/stream", "/game/action")
    assert _snap("rpg_turn_duration_seconds")[post_key] >= 1


def test_stream_server_marks_and_content_metrics(client):
    gid = _new_game(client)
    first = "rpg_turn_first_content_seconds{'route': '/game/action/stream', 'source': 'server'}.count"
    last = first.replace("first", "last")
    f0 = _snap("rpg_turn_first_content_seconds").get(first, 0)
    l0 = _snap("rpg_turn_last_content_seconds").get(last, 0)
    records = []
    lat.add_sink(records.append)
    try:
        with client.stream("POST", "/game/action/stream",
                           json={"input_text": "olho", "game_id": gid}) as r:
            _sse(r)
    finally:
        lat.remove_sink(records.append)
    assert _snap("rpg_turn_first_content_seconds")[first] == f0 + 1
    assert _snap("rpg_turn_last_content_seconds")[last] == l0 + 1
    rec = records[-1]
    assert rec["transport"] == "stream" and rec["outcome"] == "ok"
    assert rec["ack_server_ms"] is not None
    assert rec["ack_server_ms"] <= rec["ttfmc_server_ms"] <= rec["ttlt_server_ms"] <= rec["state_server_ms"]
    assert abs(sum(rec["phase_ms"].values()) - rec["total_ms"]) <= 1 or rec["total_ms"] >= sum(rec["phase_ms"].values())


def test_alert_expression_unchanged_and_route_agnostic():
    text = (ROOT / "observability/alerts/local.yml").read_text(encoding="utf-8")
    # P3: a expressao nao filtra `route`; cada serie (/game/action e /stream) dispara sozinha.
    assert 'expr: rpg_turn_duration_seconds_p95{simulated="true"} > 2' in text
    assert "route" not in text.split("TurnP95High")[1].split("OperationLeaseExpired")[0]


def test_promtool_alert_fixture_unchanged():
    promtool = shutil.which("promtool")
    if promtool is None:
        pytest.skip("promtool indisponivel neste ambiente (fixture local.test.yml inalterada)")
    done = subprocess.run([promtool, "test", "rules", "observability/alerts/local.test.yml"],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


# --- linha rpg.turn ----------------------------------------------------------

def test_rpg_turn_line_additive_fields(monkeypatch, caplog):
    usage = {"input_tokens": 100, "output_tokens": 50, "cached_tokens": 40}
    graph = _Graph([
        _attempt(ModelTier.CLASSIFY, usage=usage),
        _attempt(ModelTier.FAST, outcome="invoke_error", provider="groq"),
        _attempt(ModelTier.FAST, usage=usage, fell_back=True, index=1),
    ])
    gid = str(uuid.uuid4())
    secret_text = "texto-secreto-do-jogador-xyz"
    lines = _run_post_turn(monkeypatch, caplog, graph, text=secret_text, gid=gid)
    line = lines[-1]
    for old in ("evt", "game_id_ref", "turn", "route", "latency_ms", "events_applied",
                "llm_calls", "llm_attempts", "llm_failures", "cost_usd_est", "cost_basis"):
        assert old in line
    for new in ("action_ref", "transport", "pseudo_streaming", "ack_server_ms",
                "ttfmc_server_ms", "ttlt_server_ms", "phase_ms", "execution_mode",
                "llm_fallbacks", "llm_failed_attempts", "providers_used", "cost_usd",
                "cost_usd_basis", "lock_wait_ms", "llm_by_tier", "llm_by_phase",
                "cached_tokens", "cache_hit_ratio", "input_chars", "input_size",
                "rag_cache", "attribution"):
        assert new in line, new
    assert line["transport"] == "post" and line["ttfmc_server_ms"] is None
    assert set(line["phase_ms"]) == set(lat.PHASES)
    assert line["llm_fallbacks"] == 1 and line["llm_failed_attempts"] == 1
    assert line["providers_used"] == ["deepseek", "groq"]
    assert line["llm_by_tier"]["fast"]["attempts"] == 2
    assert line["cached_tokens"] == 80 and line["cache_hit_ratio"] == 0.4
    assert line["rag_cache"] == "not_instrumented"
    raw = json.dumps(line)
    assert secret_text not in raw and gid not in raw


def test_cost_unavailable_not_zero(monkeypatch, caplog):
    graph = _Graph([_attempt(ModelTier.FAST, usage=None)])
    line = _run_post_turn(monkeypatch, caplog, graph)[-1]
    assert line["cost_usd"] is None and line["cost_usd_basis"] == "unavailable"
    assert line["cached_tokens"] is None and line["cache_hit_ratio"] is None


def test_fallback_counts_from_attempts(monkeypatch, caplog):
    graph = _Graph([_attempt(outcome="invoke_error"), _attempt(fell_back=True, index=1,
                    usage={"input_tokens": 5, "output_tokens": 5})])
    line = _run_post_turn(monkeypatch, caplog, graph)[-1]
    assert (line["llm_fallbacks"], line["llm_failed_attempts"]) == (1, 1)
    assert line["cost_usd_basis"] == "partial"


def test_llm_attempt_attributed_to_phase(monkeypatch, caplog):
    graph = _Graph([_attempt(), _attempt(), _attempt(ModelTier.SMART)])
    line = _run_post_turn(monkeypatch, caplog, graph)[-1]
    assert sum(line["llm_by_phase"].values()) == 3
    assert line["llm_by_phase"].get("archivist") == 3   # atribuido ao no que reporta a seguir


def test_lock_wait_measured(monkeypatch, caplog):
    """Segundo turno concorrente no mesmo game_id espera o lock (FakeClock)."""
    gid = str(uuid.uuid4())
    clock = FakeClock()
    lat.set_clock(clock)
    assert persistence.save_game_state(_state(gid))
    monkeypatch.setattr(api, "game_graph", _Graph())
    caplog.set_level(logging.INFO, logger="rpg.turn")
    lock = api._game_lock(gid)
    holder_has = threading.Event()
    done = threading.Event()

    def run():
        holder_has.wait(2)
        with TestClient(api.app) as c:
            c.post("/game/action", json={"game_id": gid, "input_text": "x",
                                         "action_id": str(uuid.uuid4())})
        done.set()

    lock.acquire()
    thread = threading.Thread(target=run)
    thread.start()
    holder_has.set()
    try:
        # espera ate o worker bloquear no lock, entao avanca o relogio virtual
        import time
        time.sleep(0.3)
        clock.advance(2.0)
    finally:
        lock.release()
    thread.join(5)
    lat.set_clock(None)
    assert done.is_set()
    lines = [json.loads(r.getMessage()) for r in caplog.records
             if r.name == "rpg.turn" and json.loads(r.getMessage()).get("evt") == "turn"]
    assert lines[-1]["lock_wait_ms"] >= 2000


def test_cached_tokens_null_when_unreported(monkeypatch, caplog):
    graph = _Graph([_attempt(usage={"input_tokens": 10, "output_tokens": 5})])
    line = _run_post_turn(monkeypatch, caplog, graph)[-1]
    assert line["cached_tokens"] is None and line["cache_hit_ratio"] is None
    assert line["cost_usd_basis"] == "usage"


def test_instrumentation_equivalence(monkeypatch):
    """R16: mesmo estado final e mesmas mensagens com e sem timeline explicita."""
    from main import app as real_graph
    from playtest.runner import _build_initial_state
    outputs = []
    for with_timeline in (False, True):
        random.seed(7)
        state = _build_initial_state("explorador", 3)
        state["game_id"] = str(uuid.uuid4())
        monkeypatch.setattr(api, "game_graph", real_graph)
        kwargs = {"timeline": lat.TurnTimeline(FakeClock())} if with_timeline else {}
        random.seed(11)
        response = api._run_turn(state, "olho ao redor", str(uuid.uuid4()), **kwargs)
        saved = persistence.load_game_state(persistence.save_path(state["game_id"]))
        outputs.append((response.message, saved["world"]["turn_count"],
                        saved["player"]["gold"], saved["player"]["vitalidade"]))
    assert outputs[0] == outputs[1]


def test_disconnect_mid_stream_single_turn(monkeypatch):
    gid = str(uuid.uuid4())
    assert persistence.save_game_state(_state(gid))
    finished = threading.Event()
    action_id = str(uuid.uuid4())

    class G:
        def stream(self, current, **_kw):
            yield "updates", {"campaign_manager": {}}
            out = deepcopy(current)
            out["world"]["turn_count"] = int(out["world"].get("turn_count", 0)) + 1
            out["messages"] = list(out.get("messages") or []) + [AIMessage(content="feito")]
            yield "values", out
            finished.set()

    monkeypatch.setattr(api, "game_graph", G())
    records = []
    lat.add_sink(records.append)
    req = api.ActionRequest(game_id=gid, input_text="avanço", action_id=action_id)
    stream = api._stream_turn(req, gid)
    assert "accepted" in next(stream)
    assert "phase" in next(stream)
    stream.close()
    lat.remove_sink(records.append)
    assert finished.wait(2)
    assert records[-1]["outcome"] == "client_gone"
    assert records[-1]["ack_server_ms"] is not None
    assert records[-1]["ttfmc_server_ms"] is None and records[-1]["ttlt_server_ms"] is None
    import time
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        # load pode ver o arquivo no meio do os.replace (Windows) -> None; tenta de novo.
        loaded = persistence.load_game_state(persistence.save_path(gid)) or {}
        if action_id in (loaded.get("processed_action_ids") or []):
            break
        time.sleep(0.01)
    assert (loaded.get("world") or {}).get("turn_count") == 1


# --- revisao Sol: POST via stream x invoke ------------------------------------

def test_post_stream_mid_failure_matches_invoke_failure(monkeypatch):
    """Excecao no MEIO do stream (apos updates) = mesma semantica do invoke que
    falha: 500 generico, save intocado e o mesmo action_id pode ser repetido."""
    gid = str(uuid.uuid4())
    state = _state(gid)
    assert persistence.save_game_state(state)
    before = persistence.load_game_state(persistence.save_path(gid))

    class _MidBoom:
        def stream(self, current, **_kwargs):
            yield "updates", {"campaign_manager": {}}
            yield "updates", {"dm_router": {"next": "storyteller"}}
            raise RuntimeError("falha interna no meio")

        def invoke(self, *_a, **_k):
            raise AssertionError("POST deve usar stream quando disponivel")

    monkeypatch.setattr(api, "game_graph", _MidBoom())
    action_id = str(uuid.uuid4())
    body = {"game_id": gid, "input_text": "avanço", "action_id": action_id}
    with TestClient(api.app, raise_server_exceptions=False) as c:
        r = c.post("/game/action", json=body)
    assert r.status_code == 500
    assert "falha interna" not in r.text
    after = persistence.load_game_state(persistence.save_path(gid))
    assert after["world"] == before["world"] and after["player"] == before["player"]
    assert len(after.get("messages") or []) == len(before.get("messages") or [])

    monkeypatch.setattr(api, "game_graph", _Graph())
    with TestClient(api.app) as c:
        retry = c.post("/game/action", json=body)
    assert retry.status_code == 200, retry.text


def test_execute_graph_stream_full_state_equals_invoke():
    """O POST agora chama execute_graph com progress (stream). Estado final
    COMPLETO identico ao invoke no grafo real (MockLLM, mesma seed)."""
    from main import app as real_graph
    from playtest.runner import _build_initial_state
    from services.turn_execution import execute_graph
    base = _build_initial_state("explorador", 3)
    base["game_id"] = str(uuid.uuid4())
    base["messages"] = list(base.get("messages") or [])

    def _norm(st):
        out = {k: v for k, v in st.items() if k != "messages"}
        msgs = [(type(m).__name__, m.content) for m in st.get("messages") or []]
        return json.loads(json.dumps(out, default=str, sort_keys=True)), msgs

    random.seed(99)
    via_invoke = execute_graph(real_graph, deepcopy(base))
    random.seed(99)
    seen = []
    via_stream = execute_graph(real_graph, deepcopy(base), progress=seen.append)
    assert seen, "stream deve emitir chunks"
    assert _norm(via_stream) == _norm(via_invoke)
