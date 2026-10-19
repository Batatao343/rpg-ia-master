"""SPEC-241: access log por requisição + handler global de exceção com request_id."""

import json

import pytest

from observability import logging_setup


@pytest.fixture()
def client(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    logging_setup.configure_logging({"RPG_LOG_LEVEL": "debug", "RPG_LOG_PROPAGATE": "1"})
    from fastapi.testclient import TestClient

    return TestClient(api.app, raise_server_exceptions=False)


def _lines(capsys):
    out = []
    for raw in capsys.readouterr().out.splitlines():
        try:
            out.append(json.loads(raw))
        except ValueError:
            pass
    return out


def _req_lines(capsys):
    return [l for l in _lines(capsys) if l.get("event") == "http.request"]


def test_one_access_line_per_request(client, capsys):
    capsys.readouterr()
    r = client.get("/game/saves", headers={"X-Request-ID": "access-req-001"})
    lines = _req_lines(capsys)
    assert len(lines) == 1
    line = lines[0]
    assert line["request_id"] == "access-req-001" and line["status"] == r.status_code
    assert line["method"] == "GET" and line["route"] == "/game/saves"
    assert isinstance(line["duration_ms"], int) and line["client"] == "unknown"


def test_health_and_metrics_not_logged(client, capsys):
    capsys.readouterr()
    client.get("/health")
    assert _req_lines(capsys) == []


def test_levels_by_status(client, capsys):
    capsys.readouterr()
    client.post("/game/action", json={"input_text": "x"})
    line = _req_lines(capsys)[-1]
    assert line["level"] == "warning" and line["status"] >= 400


def test_unhandled_exception_logged_with_request_id(client, capsys):
    import api

    def boom():
        raise RuntimeError("segredo-XYZ")

    api.app.add_api_route("/__boom", boom, methods=["GET"])
    route = api.app.router.routes.pop()  # o mount estatico "/" captura tudo: vai na frente
    api.app.router.routes.insert(0, route)

    capsys.readouterr()
    try:
        r = client.get("/__boom", headers={"X-Request-ID": "boom-req-0001"})
    finally:
        api.app.router.routes.remove(route)
    assert r.status_code == 500
    body = r.json()
    assert body["request_id"] == "boom-req-0001" == r.headers["X-Request-ID"]
    assert body["detail"] == "internal_error" and body["code"] == "internal_error"
    out = capsys.readouterr().out
    assert "segredo-XYZ" not in out
    lines = [json.loads(x) for x in out.splitlines() if x.startswith("{")]
    ev = next(l for l in lines if l["event"] == "http.unhandled_exception")
    assert ev["error_type"] == "RuntimeError" and ev["request_id"] == "boom-req-0001"
    assert ev["level"] == "error" and ev["stack"] and all(":" in f for f in ev["stack"])
    access = next(l for l in lines if l["event"] == "http.request")
    assert access["status"] == 500 and access["level"] == "error"


def test_stack_has_no_exception_message():
    from observability.telemetry import safe_stack

    try:
        raise ValueError("token=abc123-secret")
    except ValueError as exc:
        frames = safe_stack(exc)
    assert "abc123" not in json.dumps(frames) and frames
    assert frames[0].startswith("tests/test_api_access_log.py:")


def test_http_exception_body_gets_request_id(client):
    r = client.get(
        "/game/state",
        params={"game_id": "00000000-0000-4000-8000-000000000000"},
        headers={"X-Request-ID": "http-exc-0001"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["request_id"] == "http-exc-0001" and body["detail"]
    assert r.headers["X-Request-ID"] == "http-exc-0001"


def test_validation_error_logs_loc_not_values(client, capsys):
    capsys.readouterr()
    r = client.post(
        "/game/action",
        headers={"X-Request-ID": "valid-req-0001"},
        json={"input_text": 12345, "game_id": "SENTINEL-VALUE-QQQ"},
    )
    assert r.status_code == 422 and r.json()["request_id"] == "valid-req-0001"
    out = capsys.readouterr().out
    assert "SENTINEL-VALUE-QQQ" not in out
    ev = next(
        json.loads(x)
        for x in out.splitlines()
        if x.startswith("{") and '"http.validation_failed"' in x
    )
    assert any("input_text" in loc for loc in ev["locs"])


def test_request_id_header_on_413_and_429(client, monkeypatch):
    r = client.post(
        "/game/new",
        content=b"x" * (70 * 1024),
        headers={"content-type": "application/json", "X-Request-ID": "big-req-00001"},
    )
    assert r.status_code == 413 and r.headers["X-Request-ID"] == "big-req-00001"
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "1")
    api._rate_hits.clear()
    codes = []
    for _ in range(40):
        resp = client.post("/game/prologue", json={})
        codes.append(resp.status_code)
        assert resp.headers.get("X-Request-ID")
    assert 429 in codes


def test_request_id_header_on_session_401(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RUNTIME_PROFILE", "hosted")
    from fastapi.testclient import TestClient

    c = TestClient(api.app, raise_server_exceptions=False)
    r = c.get("/game/saves", headers={"X-Request-ID": "sess-req-0001"})
    assert r.status_code in (401, 403, 503)
    assert r.headers["X-Request-ID"] == "sess-req-0001"


def test_build_skew_flag(client, capsys, monkeypatch):
    """SPEC-261 R2: client_build no access log; build_skew so quando o sha difere do servidor."""
    monkeypatch.setenv("GIT_SHA", "abcdef1234567890abcdef1234567890abcdef12")
    capsys.readouterr()
    client.get("/game/saves", headers={"X-RPG-Build": "abcdef1+202610191345"})
    line = _req_lines(capsys)[-1]
    assert line["client_build"] == "abcdef1+202610191345" and "build_skew" not in line
    client.get("/game/saves", headers={"X-RPG-Build": "0000000+202610191345"})
    line = _req_lines(capsys)[-1]
    assert line["build_skew"] is True
    client.get("/game/saves", headers={"X-RPG-Build": "<script>alert(1)</script>"})
    line = _req_lines(capsys)[-1]
    assert line["client_build"] == "other" and "build_skew" not in line
    client.get("/game/saves")
    assert "client_build" not in _req_lines(capsys)[-1]


def test_app_version_logged(client, capsys):
    """SPEC-259 R4: versao do app Android (formato fechado) no access log."""
    capsys.readouterr()
    client.get("/game/saves", headers={"X-RPG-Client": "android", "X-RPG-App-Version": "1.0.3+7"})
    line = _req_lines(capsys)[-1]
    assert line["app_version"] == "1.0.3+7" and line["client"] == "android"
    client.get("/game/saves", headers={"X-RPG-App-Version": "1.0 user@x.com"})
    assert _req_lines(capsys)[-1]["app_version"] == "other"


def test_deploy_args_inject_git_sha():
    """SPEC-261 R3: vercel deploy pelos scripts de staging leva GIT_SHA (runtime + build)."""
    from scripts.staging.s192 import deploy_args

    sha = "a" * 40
    assert deploy_args(["deploy", "--prod", "--yes"], sha) == [
        "deploy",
        "--prod",
        "--yes",
        "-e",
        f"GIT_SHA={sha}",
        "--build-env",
        f"GIT_SHA={sha}",
    ]
    assert deploy_args(["env", "ls"], sha) == ["env", "ls"]
    assert deploy_args(["deploy"], "") == ["deploy"]
    assert deploy_args(["deploy", "-e", "GIT_SHA=x"], sha) == ["deploy", "-e", "GIT_SHA=x"]
