"""SPEC-260 R3 — post-deploy smoke sempre escreve evidência, mesmo na falha."""

import json

import httpx

from scripts import post_deploy_smoke as smoke


def _transport(fail_path=None, status=500):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={"git_sha": "abcdef123456", "profile": "hosted-supabase", "hardened": True},
            )
        if request.url.path == fail_path:
            return httpx.Response(status)
        return httpx.Response(200, json={})

    return httpx.MockTransport(handler)


def test_failure_writes_evidence_and_continues(monkeypatch, tmp_path):
    real_run = smoke.run
    monkeypatch.setattr(
        smoke,
        "run",
        lambda u, s: real_run(u, s, transport=_transport("/auth/config", 503)),
    )
    out = tmp_path / "ev" / "smoke.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "--base-url",
            "https://rpg.example.test",
            "--expected-git-sha",
            "abcdef1",
            "--output",
            str(out),
        ],
    )
    assert smoke.main() == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["status"] == "failed"
    assert data["failed_check"] == "/auth/config"
    assert data["http_status"] == 503
    assert data["expected_git_sha"] == "abcdef1" and data["actual_git_sha"] == "abcdef123456"
    # checks independentes seguem após a 1ª falha
    assert data["checks"]["/data/map"]["status"] == "passed"
    assert all("latency_ms" in c for c in data["checks"].values())


def test_invalid_url_writes_failed_json(monkeypatch, tmp_path):
    out = tmp_path / "smoke.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "--base-url",
            "http://evil.example.test",
            "--expected-git-sha",
            "abcdef1",
            "--output",
            str(out),
        ],
    )
    assert smoke.main() == 1
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    # revisao P2/P3: mesmo schema v2 do caminho normal
    assert (
        payload["failed_checks"] == ["setup"]
        and payload["base_origin"] == "http://evil.example.test"
    )


def test_base_origin_drops_userinfo():
    assert (
        smoke._origin("https://user:segredo@rpg.example:8443/x?y=1") == "https://rpg.example:8443"
    )


def test_success_exit_zero(monkeypatch, tmp_path):
    real_run = smoke.run
    monkeypatch.setattr(smoke, "run", lambda u, s: real_run(u, s, transport=_transport()))
    out = tmp_path / "smoke.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "--base-url",
            "https://rpg.example.test",
            "--expected-git-sha",
            "abcdef1",
            "--output",
            str(out),
        ],
    )
    assert smoke.main() == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "passed"
