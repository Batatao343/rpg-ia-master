"""Revisão independente SPEC-239/240/241/245: sentinelas de privacidade num turno completo,
isolamento de contexto entre requisições concorrentes e cardinalidade de métrica."""
import json
import threading
import uuid

import anyio
import pytest

from observability import logging_setup
from observability.telemetry import (
    bind_correlation, correlation, log_event, pseudonym, request_scope,
)

SENT_TEXT = "SENTINELAJOGADOR777"
SENT_NAME = "Qzxvbrandomnome"
SENT_IP = "203.0.113.77"
SENT_TOKEN = "tokSENTINELA0123456789"
SENT_EMAIL = "sentinela.review@example.com"


@pytest.fixture()
def client(monkeypatch):
    import api
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def _json_lines(out: str) -> list[dict]:
    lines = []
    for raw in out.splitlines():
        try:
            lines.append(json.loads(raw))
        except ValueError:
            pass
    return lines


def test_full_turn_has_no_pii_sentinels(client, capsys):
    r = client.post("/game/new", json={
        "name": SENT_NAME, "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": SENT_TEXT})
    assert r.status_code == 200, r.text
    gid = r.json()["game_id"]
    action = str(uuid.uuid4())
    headers = {"X-Forwarded-For": SENT_IP, "Authorization": f"Bearer {SENT_TOKEN}",
               "Cookie": f"rpg_access={SENT_TOKEN}", "X-Request-ID": "review-req-1"}
    for path in ("/game/action", "/game/action/stream"):
        body = {"input_text": f"olho ao redor {SENT_TEXT} {SENT_EMAIL}", "game_id": gid,
                "action_id": action if path == "/game/action" else str(uuid.uuid4())}
        with client.stream("POST", path, headers=headers, json=body) as resp:
            for _ in resp.iter_lines():
                pass
            assert resp.headers.get("X-Request-ID") == "review-req-1"
    client.get("/game/nao-existe", headers=headers)
    out = capsys.readouterr().out
    rpg_lines = [line for line in _json_lines(out) if str(line.get("logger", "")).startswith("rpg")]
    assert rpg_lines
    blob = "\n".join(json.dumps(line, ensure_ascii=False) for line in rpg_lines)
    for sentinel in (SENT_TEXT, SENT_NAME, SENT_IP, SENT_TOKEN, SENT_EMAIL, gid, action):
        assert sentinel not in blob, sentinel


def test_turn_info_volume_is_bounded(client, capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info", "RPG_LOG_PROPAGATE": "1"})
    gid = client.post("/game/new", json={
        "name": "Vol", "race": "Humano", "class_name": "Sangromante",
        "region": "Nova Arcádia", "level": 1, "backstory": ""}).json()["game_id"]
    capsys.readouterr()
    r = client.post("/game/action", headers={"X-Request-ID": "review-vol-1"},
                    json={"input_text": "olho ao redor", "game_id": gid,
                          "action_id": str(uuid.uuid4())})
    assert r.status_code == 200
    mine = [line for line in _json_lines(capsys.readouterr().out)
            if line.get("request_id") == "review-vol-1"]
    # Estimativa revisada: ~4-10 linhas info por turno (MockLLM). Teto generoso contra regressão.
    assert 1 <= len(mine) <= 25, [line.get("event") for line in mine]


def test_threadpool_reuse_does_not_bleed_context():
    """Starlette roda handlers síncronos em threads reutilizadas: o bind de um request
    não pode aparecer no seguinte (anyio copia o contexto por chamada)."""
    limiter = anyio.CapacityLimiter(1)   # força a MESMA thread worker
    seen: list[dict] = []

    def handler_a():
        bind_correlation(game_id="g-A", action_id="a-A")
        return correlation()

    def handler_b():
        return correlation()

    async def run():
        with request_scope("req-A"):
            seen.append(await anyio.to_thread.run_sync(handler_a, limiter=limiter))
        with request_scope("req-B"):
            seen.append(await anyio.to_thread.run_sync(handler_b, limiter=limiter))

    anyio.run(run)
    assert seen[0]["action_ref"] == pseudonym("a-A")
    assert seen[1] == {"request_id": "req-B"}


def test_concurrent_threads_keep_own_context(capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    barrier = threading.Barrier(8)

    def worker(i: int):
        with request_scope(f"req-{i}"):
            bind_correlation(action_id=f"act-{i}")
            barrier.wait(timeout=5)
            log_event("review", "probe", idx=i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    probes = [line for line in _json_lines(capsys.readouterr().out)
              if line.get("event") == "review.probe"]
    assert len(probes) == 8
    for line in probes:
        i = line["idx"]
        assert line["request_id"] == f"req-{i}" and line["action_ref"] == pseudonym(f"act-{i}")


def test_turnstile_reason_metric_label_is_closed(monkeypatch):
    """Cardinalidade: códigos arbitrários do Turnstile não viram rótulo de métrica."""
    from observability import auth_log
    from observability.metrics import metrics
    labels: list[dict] = []
    monkeypatch.setattr(metrics, "increment", lambda name, lab=None, *a, **k: labels.append(lab))
    for i in range(30):
        auth_log.reject("captcha_rejected", f"turnstile_error:code-{i}", op="login")
    reasons = {lab["reason"] for lab in labels}
    assert reasons == {"turnstile_error"}


def test_legacy_messages_redact_raw_ids_and_ip(capsys):
    import logging
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    gid = str(uuid.uuid4())
    logging.getLogger("rpg.encounter").warning("encounter.manifest_rebuilt game=%s ip=%s", gid, SENT_IP)
    out = capsys.readouterr().out
    assert gid not in out and SENT_IP not in out
    assert "manifest_rebuilt" in out


def test_spa_navigation_and_config_reads_are_debug(client, capsys):
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    capsys.readouterr()
    client.get("/", headers={"X-Request-ID": "review-spa-1"})
    client.get("/auth/config", headers={"X-Request-ID": "review-spa-2"})
    lines = {line["request_id"]: line for line in _json_lines(capsys.readouterr().out)
             if line.get("event") == "http.request"}
    assert lines["review-spa-2"]["level"] == "debug"
    if "review-spa-1" in lines:   # "/" só existe com web/dist presente
        assert lines["review-spa-1"]["level"] == "debug"


def test_httpx_request_lines_quiet_unless_debug():
    import logging
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info", "RPG_LOG_PROPAGATE": "1"})
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.INFO)          # o SDK openai faz isto no import (OPENAI_LOG)
    rec = httpx_logger.makeRecord("httpx", logging.INFO, __file__, 1, "HTTP Request: x", (), None)
    assert not httpx_logger.filter(rec)
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    assert httpx_logger.filter(rec)
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "info", "RPG_LOG_PROPAGATE": "1"})
    assert len([f for f in httpx_logger.filters if type(f).__name__ == "_MinLevelFilter"]) == 1
