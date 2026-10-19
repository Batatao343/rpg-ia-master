"""SPEC-248: logs estruturados do roteamento LLM (tentativa, esgotamento, Mock/Fallback)."""
import json

import pytest
from langchain_core.messages import HumanMessage

import llm_setup
from llm_setup import ModelTier, RoutedLLM
from observability import logging_setup
from observability.telemetry import node_scope, request_scope

SENT = "PROMPTSENTINELA248"


class _Err(Exception):
    def __init__(self, msg, status_code=0):
        super().__init__(msg)
        self.status_code = status_code


class _Client:
    def __init__(self, behavior):
        self.behavior = behavior

    def with_structured_output(self, *a, **k):
        return self

    def invoke(self, _input):
        if self.behavior == "429":
            raise _Err(f"429 rate limit {SENT} sk-secret", 429)
        if self.behavior == "401":
            raise _Err("401 Unauthorized", 401)
        from langchain_core.messages import AIMessage
        return AIMessage(content="ok")

    def stream(self, _input):
        raise _Err("500 boom", 500)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_ROUTES", raising=False)
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})
    llm_setup.reset_llm_circuit_breakers()
    monkeypatch.setattr(llm_setup, "_ANNOUNCED", set())


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def _routed(monkeypatch, behaviors, tier=ModelTier.FAST):
    clients = {("p1", "m1"): _Client(behaviors[0]), ("p2", "m2"): _Client(behaviors[1])}
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda p, m, t: clients[(p, m)])
    return RoutedLLM(tier, 0.0, [("p1", "m1"), ("p2", "m2")])


def test_failed_attempt_logs_status_and_latency(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["429", "ok"])
    with request_scope("llm-req-000001"), node_scope("storyteller"):
        llm.invoke([HumanMessage(content=SENT)])
    attempts = [x for x in _lines(capsys) if x["event"] == "llm.attempt"]
    assert [a["outcome"] for a in attempts] == ["invoke_error", "success"]
    failed, ok = attempts
    assert failed["http_status"] == 429 and failed["error_type"] == "_Err"
    assert failed["level"] == "warning" and failed["tier"] == "fast"
    assert failed["node"] == "storyteller" and failed["request_id"] == "llm-req-000001"
    assert failed["provider"] == "p1" and failed["attempt_index"] == 0 and failed["latency_ms"] >= 0
    assert ok["level"] == "debug" and ok["fell_back"] is True


def test_circuit_open_logged(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["401", "ok"])
    llm.invoke([HumanMessage(content="a")])      # 401 abre o circuito
    capsys.readouterr()
    llm.invoke([HumanMessage(content="b")])
    attempts = [x for x in _lines(capsys) if x["event"] == "llm.attempt"]
    assert attempts[0]["outcome"] == "circuit_open" and attempts[0]["level"] == "warning"
    assert "Unauthorized" not in json.dumps(attempts)      # texto do provider fica fora do log


def test_kill_switch_logged(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["ok", "ok"])
    monkeypatch.setattr(llm_setup, "_kill_switch_disabled", lambda p, m: p == "p1")
    llm.invoke([HumanMessage(content="a")])
    attempts = [x for x in _lines(capsys) if x["event"] == "llm.attempt"]
    assert [a["outcome"] for a in attempts] == ["kill_switch", "success"]


def test_exhausted_logged_with_node(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["429", "401"])
    with node_scope("archivist"):
        result = llm.invoke([HumanMessage(content=SENT)])
    assert result.content == ""
    (line,) = [x for x in _lines(capsys) if x["event"] == "llm.exhausted"]
    assert line["level"] == "error" and line["tier"] == "fast" and line["node"] == "archivist"
    assert [a["provider"] for a in line["attempts"]] == ["p1", "p2"]
    assert all(a["outcome"] == "invoke" for a in line["attempts"])


def test_stream_failure_logs_http_status(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["ok", "ok"])
    list(llm.stream([HumanMessage(content="a")]))
    attempts = [x for x in _lines(capsys) if x["event"] == "llm.attempt"]
    assert attempts and attempts[0]["outcome"] == "stream_error" and attempts[0]["http_status"] == 500


def test_mock_selected_logged_once(capsys, monkeypatch):
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    llm_setup.get_llm()
    llm_setup.get_llm()
    lines = [x for x in _lines(capsys) if x["event"] == "llm.mock_selected"]
    assert len(lines) == 1 and lines[0]["reason"] == "force_mock" and lines[0]["level"] == "warning"


def test_mock_selected_is_error_outside_legacy(capsys, monkeypatch):
    monkeypatch.setenv("RPG_FORCE_MOCK", "1")
    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted-supabase")
    llm_setup.get_llm()
    (line,) = [x for x in _lines(capsys) if x["event"] == "llm.mock_selected"]
    assert line["level"] == "error"


def test_fallback_llm_selected_logged(capsys, monkeypatch):
    for env in set(llm_setup.PROVIDER_KEY_ENV.values()):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("RPG_NO_MOCK", "1")
    llm_setup.get_llm()
    (line,) = [x for x in _lines(capsys) if x["event"] == "llm.fallback_llm_selected"]
    assert line["reason"] == "no_keys" and line["level"] == "error"


def test_routes_invalid_never_logs_the_env_json(capsys, monkeypatch, tmp_path):
    bad = tmp_path / "routes.json"
    bad.write_text('{"fast": [["deepseek", SECRET-NOT-JSON', encoding="utf-8")
    monkeypatch.setenv("RPG_ROUTES", str(bad))
    llm_setup._load_routes()
    out = capsys.readouterr().out
    (line,) = [json.loads(x) for x in out.splitlines() if "llm.routes_invalid" in x]
    assert line["error_type"] and "SECRET-NOT-JSON" not in out


def test_no_prompt_in_llm_logs(capsys, monkeypatch):
    llm = _routed(monkeypatch, ["429", "401"])
    llm.invoke([HumanMessage(content=SENT)])
    list(llm.stream([HumanMessage(content=SENT)]))
    out = capsys.readouterr().out
    assert out and SENT not in out and "sk-secret" not in out


def test_turn_line_aggregates_errors_and_http_statuses():
    import api
    attempts = [
        {"provider": "p1", "model": "m", "tier": "fast", "outcome": "invoke_error", "network_attempted": True,
         "error_type": "_Err", "http_status": 429, "usage": None},
        {"provider": "p2", "model": "m", "tier": "fast", "outcome": "success", "network_attempted": True,
         "error_type": None, "http_status": 0, "usage": None},
    ]
    fields = api._llm_log_fields([{"provider": "p2", "fell_back": True}], attempts)
    assert fields["llm_errors"] == {"_Err": 1} and fields["llm_http_statuses"] == {"429": 1}
