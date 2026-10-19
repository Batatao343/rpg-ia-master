"""SPEC-246: 429/413/503-de-limite com linha JSON (retry_after_s, request_id) e limiter fail-open visivel."""
import ast
import asyncio
import json
from pathlib import Path

import pytest

from observability import logging_setup
from observability.telemetry import request_scope
from services import abuse_policy

ROOT = Path(__file__).resolve().parents[1]
IP = "203.0.113.77"
OWNER = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def _logs():
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug"})
    abuse_policy._block_log_last.clear()
    yield
    abuse_policy._block_log_last.clear()


def _lines(capsys, prefix=""):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if str(row.get("event", "")).startswith(prefix):
            out.append(row)
    return out


def test_record_block_json_with_retry_after(capsys):
    with request_scope("abuse-req-0001"):
        abuse_policy.record_block("turn", "owner", owner=OWNER, retry_after=17, limit=20)
    out = capsys.readouterr().out
    assert OWNER not in out
    row = next(json.loads(x) for x in out.splitlines() if '"abuse.blocked"' in x)
    assert row["retry_after_s"] == 17 and row["limit"] == 20
    assert row["request_id"] == "abuse-req-0001" and row["level"] == "warning"
    assert row["cls"] == "turn" and row["scope"] == "owner" and len(row["owner_ref"]) == 16


def test_record_block_sampled_per_key(capsys):
    from observability.metrics import metrics
    before = metrics._values.get(("rpg_rate_limited_total", (("class", "turn"), ("scope", "ip"))), 0)
    for _ in range(5):
        abuse_policy.record_block("turn", "ip", ip=IP, retry_after=3)
    rows = _lines(capsys, "abuse.blocked")
    assert len(rows) == 1                     # 1x/min por (classe, escopo, chave)
    after = metrics._values.get(("rpg_rate_limited_total", (("class", "turn"), ("scope", "ip"))), 0)
    assert after - before == 5                # a metrica conta todos
    assert IP not in json.dumps(rows)
    abuse_policy.record_block("turn", "ip", ip="198.51.100.9", retry_after=3)
    assert len(_lines(capsys, "abuse.blocked")) == 1        # outra chave: loga


def test_body_limit_logs_and_counts(capsys):
    from observability.metrics import metrics
    from services.body_limit import BodyLimitMiddleware

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = BodyLimitMiddleware(inner, default_limit=10, per_path={"/game/new": 10})
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(m):
        sent.append(m)

    key = ("rpg_http_body_too_large_total", (("route", "/game/new"),))
    before = metrics._values.get(key, 0)
    with request_scope("body-req-00001"):
        asyncio.run(app({"type": "http", "method": "POST", "path": "/game/new",
                         "headers": [(b"content-length", b"999")]}, receive, send))
    assert sent[0]["status"] == 413
    row = _lines(capsys, "http.body_too_large")[0]
    assert row["route"] == "/game/new" and row["limit_bytes"] == 10 and row["declared_bytes"] == 999
    assert row["request_id"] == "body-req-00001"
    assert metrics._values.get(key, 0) - before == 1


def test_body_limit_route_label_is_templated():
    from api import app
    from services.body_limit import route_label
    assert route_label("/game/8a6e0804-2bd0-4672-b79d-d97358571b25/audit-export",
                       routes=app.routes) == "/game/{id}/audit-export"


def test_body_limit_route_label_closed_for_unknown_paths(capsys):
    """Revisao P2/P3: path aleatorio (inexistente) nunca vira rotulo nem campo de log."""
    from fastapi.testclient import TestClient
    from api import app
    from observability.metrics import metrics
    from services.body_limit import route_label
    assert route_label("/nao/existe/abc123") == "other"
    assert route_label("/nao/existe/abc123", routes=app.routes) == "other"
    before = {k for k in metrics._values if k[0] == "rpg_http_body_too_large_total"}
    with TestClient(app) as client:
        for i in range(3):
            client.post(f"/random-{i}-zzz", content=b"x" * (256 * 1024 + 1))
    rows = _lines(capsys, "http.body_too_large")
    assert rows and all(r["route"] == "other" for r in rows)
    new = {k for k in metrics._values if k[0] == "rpg_http_body_too_large_total"} - before
    assert all(dict(k[1])["route"] in {"other"} for k in new)


def test_limiter_exception_logged_failopen(capsys):
    from observability.metrics import metrics
    key = ("rpg_rate_limiter_errors_total", (("site", "daily_quota"),))
    before = metrics._values.get(key, 0)

    class Boom(RuntimeError):
        pass

    abuse_policy.limiter_unavailable("daily_quota", Boom("dsn=postgres://u:p@h/db"))
    out = capsys.readouterr().out
    assert "postgres://" not in out
    row = next(json.loads(x) for x in out.splitlines() if '"abuse.limiter_unavailable"' in x)
    assert row["level"] == "error" and row["error_type"] == "Boom" and row["site"] == "daily_quota"
    assert metrics._values.get(key, 0) - before == 1


def test_owner_rate_limit_failopen_is_logged(monkeypatch, capsys):
    import api
    from types import SimpleNamespace

    class Broken:
        def consume(self, *a, **k):
            raise ConnectionError("down")

    monkeypatch.setattr("infrastructure.runtime.get_runtime",
                        lambda: SimpleNamespace(rate_limiter=Broken()))
    monkeypatch.delenv("RPG_RATE_LIMIT", raising=False)
    request = SimpleNamespace(method="POST", url=SimpleNamespace(path="/game/chronicle/search"))
    assert api._owner_rate_limit(request, SimpleNamespace(user_id=OWNER)) is None   # continua fail-open
    rows = _lines(capsys, "abuse.limiter_unavailable")
    assert rows and rows[0]["site"] == "owner_minute" and rows[0]["error_type"] == "ConnectionError"


def _calls_in(node: ast.AST) -> set[str]:
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            names.add(func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", ""))
    return names


def test_every_429_records_block():
    """Toda funcao de api.py que responde 429/413 chama record_block / log de body (R2)."""
    tree = ast.parse((ROOT / "api.py").read_text(encoding="utf-8"))
    offenders = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for sub in ast.walk(fn):
            if not isinstance(sub, ast.Call):
                continue
            first = sub.args[0] if sub.args else None
            code = first.value if isinstance(first, ast.Constant) else None
            if code not in (429, 413):
                continue
            name = sub.func.attr if isinstance(sub.func, ast.Attribute) else getattr(sub.func, "id", "")
            if name not in {"HTTPException", "_error_response", "SpeechError"}:
                continue
            needed = {"record_block"} if code == 429 else {"log_body_too_large"}
            if not (needed & _calls_in(fn)):
                offenders.append(f"{fn.name}:{sub.lineno}:{code}")
    assert not offenders, offenders
