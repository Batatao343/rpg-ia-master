"""SPEC-221: /metrics com Bearer, cache/HSTS/CSP, teto de body (413) e filename ASCII seguro."""
from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

import api
import persistence
from services.body_limit import BodyLimitMiddleware, safe_attachment_filename

TOKEN = "t" * 40


@pytest.fixture()
def client():
    return TestClient(api.app)


@pytest.fixture(autouse=True)
def _reset_cache():
    api._metrics_sql_cache.reset()
    yield
    api._metrics_sql_cache.reset()


# ---- R1-R3 -----------------------------------------------------------------
def test_metrics_db_profile_sem_token_ou_errado_404(client, monkeypatch):
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(api, "_load_metrics_sql", lambda: None)
    monkeypatch.setenv("RPG_METRICS_TOKEN", TOKEN)
    assert client.get("/metrics").status_code == 404
    assert client.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code == 404
    ok = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("text/plain; version=0.0.4")


def test_metrics_db_profile_sem_env_ou_token_curto_fecha(client, monkeypatch):
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(api, "_load_metrics_sql", lambda: None)
    monkeypatch.delenv("RPG_METRICS_TOKEN", raising=False)
    assert client.get("/metrics").status_code == 404
    monkeypatch.setenv("RPG_METRICS_TOKEN", "curto")
    assert client.get("/metrics", headers={"Authorization": "Bearer curto"}).status_code == 404


def test_metrics_legacy_sem_env_aberto_e_com_env_exige(client, monkeypatch):
    monkeypatch.delenv("RPG_METRICS_TOKEN", raising=False)
    assert client.get("/metrics").status_code == 200
    monkeypatch.setenv("RPG_METRICS_TOKEN", TOKEN)
    assert client.get("/metrics").status_code == 404


def test_metrics_sql_cacheado_e_erro_vira_gauge(client, monkeypatch):
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_METRICS_TOKEN", TOKEN)
    calls = []

    def boom():  # simula get_runtime/pool falhando dentro do loader real
        calls.append(1)

    monkeypatch.setattr(api, "_load_metrics_sql", boom)
    h = {"Authorization": f"Bearer {TOKEN}"}
    client.get("/metrics", headers=h)
    client.get("/metrics", headers=h)
    assert len(calls) == 1

    monkeypatch.undo()
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setenv("RPG_METRICS_TOKEN", TOKEN)
    api._metrics_sql_cache.reset()
    import infrastructure.runtime as rt
    monkeypatch.setattr(rt, "get_runtime", lambda: (_ for _ in ()).throw(RuntimeError("db")))
    r = client.get("/metrics", headers=h)
    assert r.status_code == 200
    assert "rpg_metrics_db_error 1" in r.text


# ---- R4/R5 -----------------------------------------------------------------
def test_no_store_em_game_account_auth_mas_nao_em_data(client):
    assert client.get("/auth/config").headers["cache-control"] == "no-store"
    assert client.get("/game/saves").headers["cache-control"] == "no-store"
    assert "no-store" not in client.get("/data/options").headers.get("cache-control", "")


def test_hsts_so_com_cookie_secure(client, monkeypatch):
    monkeypatch.delenv("RPG_COOKIE_SECURE", raising=False)
    assert "strict-transport-security" not in client.get("/health").headers
    monkeypatch.setenv("RPG_COOKIE_SECURE", "1")
    hsts = client.get("/health").headers["strict-transport-security"]
    assert hsts == "max-age=63072000; includeSubDomains"
    assert "preload" not in hsts


def test_csp_tem_form_action(client):
    assert "form-action 'self'" in client.get("/health").headers["content-security-policy"]


# ---- R6 --------------------------------------------------------------------
def test_body_acima_do_limite_413_por_content_length(client):
    r = client.post("/auth/login", content=b"x" * (300 * 1024),
                    headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert r.json() == {"detail": "payload_too_large"}


def test_body_dentro_do_limite_passa_ao_handler(client):
    r = client.post("/auth/login", json={"email": "a", "password": "b"})
    assert r.status_code != 413  # 422 de validacao


def test_413_por_contagem_sem_content_length():
    seen = {}

    async def inner(scope, receive, send):
        body = b""
        while True:
            m = await receive()
            body += m.get("body", b"")
            if not m.get("more_body"):
                break
        seen["len"] = len(body)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = BodyLimitMiddleware(inner, default_limit=10, per_path={"/big": 100})
    chunks = [{"type": "http.request", "body": b"a" * 8, "more_body": True},
              {"type": "http.request", "body": b"a" * 8, "more_body": False}]
    sent = []

    async def run(path):
        sent.clear()
        queue = list(chunks)

        async def receive():
            return queue.pop(0)

        async def send(m):
            sent.append(m)

        await app({"type": "http", "method": "POST", "path": path, "headers": []}, receive, send)

    asyncio.run(run("/x"))
    assert sent[0]["status"] == 413 and len(sent) == 2
    asyncio.run(run("/big"))
    assert sent[0]["status"] == 200


# ---- R7 --------------------------------------------------------------------
def test_safe_filename_unicode_e_vazio():
    a, q = safe_attachment_filename("Ωmega")
    assert a == "mega" and a.isascii() and "%" in q
    assert safe_attachment_filename("José-Ângelo")[0] == "Jose-Angelo"
    assert safe_attachment_filename("") == ("cronica", "cronica")
    assert safe_attachment_filename("ΩΩ")[0] == "cronica"
    assert len(safe_attachment_filename("a" * 200)[0]) == 40


@pytest.mark.parametrize("name", ["Ωmega", "José-Ângelo", "", "../../x\r\ny"])
def test_export_cronica_nome_unicode_nunca_500(client, tmp_path, monkeypatch, name):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    gid = str(uuid.uuid4())
    data = {"schema_version": persistence.SCHEMA_VERSION, "game_id": gid,
            "player": {"name": name, "class_name": "X", "level": 1, "inventory": [],
                       "known_abilities": []},
            "world": {"current_location": "Nova Arcádia"}, "message_history": [],
            "chronicle": []}
    with open(os.path.join(str(tmp_path), f"{gid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    r = client.get("/game/chronicle/export", params={"game_id": gid})
    assert r.status_code == 200
    cd = r.headers["content-disposition"]
    assert 'filename="cronica_' in cd and "filename*=UTF-8''cronica_" in cd
    assert "\r" not in cd and "\n" not in cd


# ---- R6 (revisao Sol): usos legitimos no teto -------------------------------
def test_game_new_maximo_legitimo_cabe_no_teto_64k():
    """Pior caso legitimo de /game/new (todos os campos no max_length, 4 bytes/char UTF-8)."""
    from services.prologue import MAX_BEAT_CHARS
    c = "\U0001F525"  # 4 bytes em UTF-8 (pior caso sem \u-escape, como o browser envia)
    body = {
        "name": c * 80, "race": c * 40, "class_name": c * 40, "region": c * 60, "level": 20,
        "backstory": c * 2000, "appearance": c * 1000, "visual_exclusions": c * 500,
        "action_id": str(uuid.uuid4()),
        "scenario": {"prologue": c * 2000, "opening_scene_brief": c * 1200, "arc_title": c * 80,
                     "beats": [c * MAX_BEAT_CHARS] * 5, "climax": c * 300,
                     "seed_npcs": [{"name": c * 60, "role": c * 80, "attitude": c * 20,
                                    "persona": c * 400}] * 2},
    }
    size = len(json.dumps(body, ensure_ascii=False).encode())
    assert size < 64 * 1024, size


def test_stt_8mib_e_stripe_nao_cortados_pelo_middleware(client):
    r = client.post("/account/transcriptions", content=b"\0" * (8 * 1024 * 1024),
                    headers={"content-type": "audio/wav"})
    assert r.status_code != 413 or r.json().get("detail") != "payload_too_large"
    r = client.post("/payments/stripe/webhook", content=b"x" * (300 * 1024))
    assert r.json().get("detail") != "payload_too_large"  # handler decide (503/413 proprio)


def test_metrics_rate_limit_so_para_sondas_scraper_autenticado_livre(client, monkeypatch):
    """Revisao Sol: scrape de 5 s (12/min) do stack SPEC-106 nao pode cair em 429."""
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr(api, "_load_metrics_sql", lambda: None)
    monkeypatch.setenv("RPG_METRICS_TOKEN", TOKEN)
    monkeypatch.setenv("RPG_RATE_LIMIT", "30")
    api._metrics_hits.clear()
    h = {"Authorization": f"Bearer {TOKEN}"}
    try:
        assert all(client.get("/metrics", headers=h).status_code == 200 for _ in range(20))
        codes = [client.get("/metrics").status_code for _ in range(13)]
        assert codes[:12] == [404] * 12 and codes[12] == 429
    finally:
        api._metrics_hits.clear()
