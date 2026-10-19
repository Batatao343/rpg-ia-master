"""SPEC-219: classes de rota, limites por IP/owner, cota diaria por owner e IP real atras de proxy."""

from __future__ import annotations

import ast
import re
from datetime import datetime, timezone, UTC
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api
from infrastructure.contracts import Principal, Unauthorized
from infrastructure.local_adapters import MemoryRateLimiter
from infrastructure.request_context import reset_current_principal, set_current_principal
from services import abuse_policy as ap
from services.auth_sessions import CsrfSigner

ORIGIN = "http://localhost:5173"
SECRET = "s" * 32
GAME = "6f1c1c0e-5d0e-4e0e-9a3e-0b0e0e0e0e0e"
ART = "7f1c1c0e-5d0e-4e0e-9a3e-0b0e0e0e0e0e"


# --- R1: classificacao ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("POST", "/game/action", "turn"),
        ("POST", "/game/action/stream", "turn"),
        ("POST", "/game/death", "turn"),
        ("POST", "/game/new", "llm_aux"),
        ("POST", "/game/prologue", "llm_aux"),
        ("POST", "/game/art/brief", "llm_aux"),
        ("POST", "/game/combat-simulator", "llm_aux"),
        ("POST", "/game/chronicle/search", "embedding"),
        ("POST", f"/game/{GAME}/art/quote", "quote"),
        ("POST", f"/game/{GAME}/art/confirm", "quote"),
        ("POST", f"/game/{GAME}/art/player/confirm", "quote"),
        ("POST", "/game/equip", "mutation"),
        ("POST", "/game/levelup", "mutation"),
        ("POST", "/game/cards/prepare", "mutation"),
        ("DELETE", f"/game/save/{GAME}", "mutation"),
        ("POST", f"/game/{GAME}/art/{ART}/quality", "mutation"),
        ("POST", "/account/checkout", "payments"),
        ("POST", "/account/purchases/google/verify", "payments"),
        ("POST", f"/game/{GAME}/audit-export", "export"),
        ("GET", "/account/export", "export"),
        ("POST", "/account/transcriptions", "stt"),
        ("POST", "/telemetry/client-latency", "latency"),
        ("GET", "/game/state", "read_auth"),
        ("GET", "/account/balance", "read_auth"),
        ("GET", f"/game/{GAME}/operations/{ART}", "read_auth"),
        ("GET", "/health", None),
        ("POST", "/auth/login", None),
        ("GET", "/game/action", "read_auth"),  # GET nao e o turno
        ("POST", "/game/action/extra", None),
    ],
)
def test_classify(method, path, expected):
    cls = ap.classify(method, path)
    assert (cls.name if cls else None) == expected


def test_every_money_route_in_api_has_a_class():
    """Anti-esquecimento: toda rota POST/DELETE /game|/account do app tem classe (ou esta isenta)."""
    exempt = {"/account/delete", "/account/reauth", "/payments/stripe/webhook"}
    missing = []
    for route in api.app.routes:
        path = getattr(route, "path", "")
        if not path.startswith(("/game", "/account")) or path in exempt:
            continue
        for method in getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}:
            concrete = re.sub(r"\{[^}]+\}", GAME, path)
            if ap.classify(method, concrete) is None:
                missing.append((method, path))
    assert missing == []


# --- limites / env ----------------------------------------------------------------------------


def test_limits_defaults_and_overrides():
    turn = ap.ROUTE_CLASSES["turn"]
    assert ap.limits_for(turn, {}) == (60, 20)
    assert ap.limits_for(ap.ROUTE_CLASSES["embedding"], {}) == (30, 10)
    assert ap.limits_for(ap.ROUTE_CLASSES["payments"], {}) == (15, 5)
    assert ap.limits_for(turn, {"RPG_LIMIT_TURN_OWNER": "7", "RPG_LIMIT_TURN_IP": "9"}) == (9, 7)
    # legado: RPG_RATE_LIMIT vira o limite de IP (menos leitura); 0 desliga tudo por minuto
    assert ap.limits_for(turn, {"RPG_RATE_LIMIT": "30"}) == (30, 20)
    assert ap.limits_for(ap.ROUTE_CLASSES["read_auth"], {"RPG_RATE_LIMIT": "30"}) == (300, 120)
    assert ap.limits_for(turn, {"RPG_RATE_LIMIT": "0"}) == (0, 0)
    assert ap.limits_for(turn, {"RPG_LIMIT_TURN_OWNER": "abc"}) == (60, 20)
    assert (
        ap.daily_quota_limit({}) == 600 and ap.daily_quota_limit({"RPG_DAILY_TURN_QUOTA": "0"}) == 0
    )


# --- R4: IP real ------------------------------------------------------------------------------


def _req(headers=None, host="10.0.0.9"):
    return SimpleNamespace(
        headers={k.lower(): v for k, v in (headers or {}).items()},
        client=SimpleNamespace(host=host),
    )


def test_client_ip_default_ignores_forwarded_headers():
    r = _req({"x-forwarded-for": "6.6.6.6", "x-vercel-forwarded-for": "7.7.7.7"})
    assert ap.client_ip(r, {}) == "10.0.0.9"


def test_client_ip_vercel_mode_uses_platform_header():
    r = _req({"x-vercel-forwarded-for": "203.0.113.5, 10.1.1.1", "x-forwarded-for": "6.6.6.6"})
    assert ap.client_ip(r, {"VERCEL": "1"}) == "203.0.113.5"
    assert ap.client_ip(_req({"x-real-ip": "198.51.100.7"}), {"VERCEL": "1"}) == "198.51.100.7"
    assert ap.client_ip(_req(), {"VERCEL": "1"}) == "10.0.0.9"  # ausente
    assert (
        ap.client_ip(_req({"x-vercel-forwarded-for": "not an ip!"}), {"VERCEL": "1"}) == "10.0.0.9"
    )


def test_client_ip_trusted_hops_takes_nth_from_the_right():
    r = _req({"x-forwarded-for": "6.6.6.6, 203.0.113.5, 10.1.1.1"})
    assert ap.client_ip(r, {"RPG_TRUSTED_PROXY_HOPS": "1"}) == "10.1.1.1"
    assert ap.client_ip(r, {"RPG_TRUSTED_PROXY_HOPS": "2"}) == "203.0.113.5"
    assert (
        ap.client_ip(r, {"RPG_TRUSTED_PROXY_HOPS": "9"}) == "10.0.0.9"
    )  # menos saltos que o configurado
    assert ap.client_ip(r, {"RPG_TRUSTED_PROXY_HOPS": "x"}) == "10.0.0.9"
    assert (
        ap.client_ip(_req({"x-forwarded-for": "garbage"}), {"RPG_TRUSTED_PROXY_HOPS": "1"})
        == "10.0.0.9"
    )


def test_client_ip_never_raises():
    assert ap.client_ip(object(), {}) == "unknown"
    assert ap.client_ip(SimpleNamespace(headers=None, client=None), {"VERCEL": "1"}) == "unknown"


def test_account_security_and_captcha_use_client_ip(monkeypatch):
    from services import account_security

    monkeypatch.setenv("RPG_TRUSTED_PROXY_HOPS", "1")
    r = _req({"x-forwarded-for": "6.6.6.6, 203.0.113.5"})
    assert account_security._remote(r) == "203.0.113.5"
    assert "remote_ip=_client_ip(request)" in Path("api.py").read_text(encoding="utf-8")


# --- R3: cota diaria (memoria) ----------------------------------------------------------------


def test_memory_daily_quota_limits_per_owner_and_day():
    q = ap.MemoryDailyQuota()
    a, b = uuid4(), uuid4()
    noon = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
    for _ in range(600):
        assert q.bump(a, "turn", 600, now=noon).allowed
    denied = q.bump(a, "turn", 600, now=noon)
    assert not denied.allowed and denied.retry_after_seconds == 12 * 3600
    assert q.bump(b, "turn", 600, now=noon).allowed  # outro owner
    assert q.bump(a, "llm_aux", 600, now=noon).allowed  # outra classe
    assert q.bump(a, "turn", 600, now=datetime(2026, 10, 18, 0, 0, 1, tzinfo=UTC)).allowed


# --- API em perfil DB (identidade/limiter/cota falsos) ---------------------------------------


class FakeIdentity:
    def __init__(self):
        self.calls = 0
        self.owners = {"tok-a": uuid4(), "tok-b": uuid4()}

    def verify(self, token):
        self.calls += 1
        if token in self.owners:
            owner = self.owners[token]
            return Principal(owner, "auth", str(owner))
        raise Unauthorized("token inválido")


@pytest.fixture
def env(monkeypatch):
    identity = FakeIdentity()
    runtime = SimpleNamespace(
        identity_verifier=identity,
        rate_limiter=MemoryRateLimiter(),
        daily_quota=ap.MemoryDailyQuota(),
        turn_coordinator=None,
    )
    monkeypatch.setenv("RPG_SESSION_SECRET", SECRET)
    monkeypatch.delenv("RPG_RATE_LIMIT", raising=False)  # a suite liga 0; aqui queremos o real
    monkeypatch.delenv("RPG_DAILY_TURN_QUOTA", raising=False)
    monkeypatch.setattr(api, "_database_profile", lambda: True)
    monkeypatch.setattr("infrastructure.runtime.get_runtime", lambda: runtime)
    api._authfail_until.clear()
    client = TestClient(api.app, raise_server_exceptions=False)
    client.headers["Origin"] = ORIGIN
    token = CsrfSigner(SECRET).issue()
    client.cookies.set("rpg_csrf", token)
    client.headers["X-CSRF-Token"] = token
    yield client, identity, runtime
    api._authfail_until.clear()  # nao vaza bloqueio para outros arquivos


def _as(client, token):
    for cookie in [c for c in client.cookies.jar if c.name == "rpg_access"]:
        client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
    client.cookies.set("rpg_access", token)


def _search(client):
    return client.post("/game/chronicle/search", json={"game_id": GAME, "query": "x"})


def test_chronicle_search_is_limited_per_owner(env):
    client, _identity, _rt = env
    _as(client, "tok-a")
    codes = [_search(client).status_code for _ in range(11)]
    assert 429 not in codes[:10] and codes[10] == 429
    body = _search(client)
    assert body.status_code == 429
    assert body.json()["detail"] == "rate_limited" and body.json()["scope"] == "owner"
    assert body.headers["Retry-After"].isdigit() and body.json()["retry_after_seconds"] >= 1


def test_two_owners_on_same_ip_do_not_share_owner_bucket(env):
    client, _identity, _rt = env
    _as(client, "tok-a")
    for _ in range(11):
        _search(client)
    assert _search(client).status_code == 429
    _as(client, "tok-b")
    assert _search(client).status_code != 429  # B nao paga pelo abuso de A


def test_ip_limit_is_per_class_and_shared_by_owners(env, monkeypatch):
    client, _identity, _rt = env
    monkeypatch.setenv("RPG_LIMIT_EMBEDDING_IP", "4")
    monkeypatch.setenv("RPG_LIMIT_EMBEDDING_OWNER", "1000")
    _as(client, "tok-a")
    assert [_search(client).status_code for _ in range(4)].count(429) == 0
    _as(client, "tok-b")
    out = _search(client)
    assert out.status_code == 429 and out.json()["scope"] == "ip"
    assert client.get("/account/balance").status_code != 429  # outra classe, mesmo IP: intacta


def test_payments_quote_and_export_classes_are_limited(env):
    client, _identity, _rt = env
    _as(client, "tok-a")
    res = [
        client.post(
            "/account/checkout", json={"sku_id": "x", "request_id": str(uuid4())}
        ).status_code
        for _ in range(6)
    ]
    assert res[5] == 429 and 429 not in res[:5]
    res = [client.post(f"/game/{GAME}/art/quote", json={}).status_code for _ in range(11)]
    assert res[10] == 429 and 429 not in res[:10]
    res = [client.get("/account/export").status_code for _ in range(7)]
    assert res[6] == 429


def test_rate_limit_zero_disables_every_minute_limit(env, monkeypatch):
    client, _identity, _rt = env
    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    _as(client, "tok-a")
    assert 429 not in [_search(client).status_code for _ in range(40)]


def test_blocks_are_counted_in_metrics_without_ids(env):
    from observability.metrics import metrics

    client, _identity, _rt = env
    _as(client, "tok-a")
    for _ in range(12):
        _search(client)
    keys = [k for k in metrics._values if k[0] == "rpg_rate_limited_total"]
    assert keys and all({name for name, _ in k[1]} == {"class", "scope"} for k in keys)


# --- turnos: owner/min + cota diaria, replay nao consome, SSE 1x ------------------------------


def _as_principal(owner):
    return set_current_principal(Principal(owner, "auth", str(owner)))


def test_turn_budget_minute_then_daily(env, monkeypatch):
    token = _as_principal(uuid4())
    try:
        for _ in range(20):
            api._enforce_owner_budget("turn", minute=True)
        with pytest.raises(api.QuotaExceeded) as exc:
            api._enforce_owner_budget("turn", minute=True)
        assert exc.value.scope == "owner" and exc.value.status_code == 429
    finally:
        reset_current_principal(token)
    monkeypatch.setenv("RPG_DAILY_TURN_QUOTA", "3")
    token = _as_principal(uuid4())
    try:
        for _ in range(3):
            api._enforce_owner_budget("turn", minute=True)
        with pytest.raises(api.QuotaExceeded) as exc:
            api._enforce_owner_budget("turn", minute=True)
        assert exc.value.detail == "daily_quota_exceeded" and exc.value.scope == "daily"
        assert exc.value.retry_after_seconds >= 1
    finally:
        reset_current_principal(token)


def test_daily_quota_zero_disables_and_legacy_profile_skips(env, monkeypatch):
    token = _as_principal(uuid4())
    try:
        monkeypatch.setenv("RPG_DAILY_TURN_QUOTA", "0")
        for _ in range(5):
            api._enforce_owner_budget("turn", minute=False)
        monkeypatch.setenv("RPG_DAILY_TURN_QUOTA", "1")
        monkeypatch.setattr(api, "_database_profile", lambda: False)  # R11: legacy so IP
        for _ in range(5):
            api._enforce_owner_budget("turn", minute=True)
    finally:
        reset_current_principal(token)


def test_quota_backend_failure_does_not_take_the_game_down(env):
    _client, _identity, runtime = env

    class Boom:
        def bump(self, *a, **k):
            raise RuntimeError("db down")

    runtime.daily_quota = Boom()
    token = _as_principal(uuid4())
    try:
        api._enforce_owner_budget("turn", minute=False)
    finally:
        reset_current_principal(token)


def _patched_execute(monkeypatch, receipt):
    state = {"game_id": GAME}
    monkeypatch.setattr(api, "load_game_state", lambda _f: state)
    monkeypatch.setattr(api, "_resolve_save_file", lambda _g: "x")
    monkeypatch.setattr(api, "_await_projection_db", lambda s, _g: s)
    monkeypatch.setattr(api, "_begin_turn_operation", lambda s, r: (None, "h", receipt))
    monkeypatch.setattr(api, "_action_already_processed", lambda s, a: False)
    monkeypatch.setattr(api, "_apply_action_options", lambda s, r: None)
    monkeypatch.setattr(api, "_projection_owner", lambda: None)
    monkeypatch.setattr(api, "_run_turn", lambda *a, **k: "TURN-RESPONSE")


def test_replay_by_action_id_does_not_consume_quota(env, monkeypatch):
    _client, _identity, runtime = env
    monkeypatch.setenv("RPG_DAILY_TURN_QUOTA", "2")
    _patched_execute(monkeypatch, receipt="RECEIPT")
    token = _as_principal(uuid4())
    req = api.ActionRequest(input_text="olho", game_id=GAME, action_id=str(uuid4()))
    try:
        for _ in range(10):  # replays: nunca consomem
            assert api._execute_action(req) == "RECEIPT"
        assert runtime.daily_quota._counts == {}
        _patched_execute(monkeypatch, receipt=None)
        assert api._execute_action(req) == "TURN-RESPONSE"
        assert api._execute_action(req) == "TURN-RESPONSE"
        with pytest.raises(api.QuotaExceeded):
            api._execute_action(req)
    finally:
        reset_current_principal(token)


def test_stream_and_post_share_the_single_per_turn_check():
    """R10: o SSE reaproveita _execute_action (1 consumo por turno, nao por chunk)."""
    tree = ast.parse(Path("api.py").read_text(encoding="utf-8"))
    functions = {fn.name: fn for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)}

    def calls(name):
        return {
            n.func.id
            for n in ast.walk(functions[name])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }

    assert "_execute_action" in calls("game_action") and "_execute_action" in calls(
        "_stream_turn_events"
    )
    owners = sorted(
        name
        for name in functions
        if "_enforce_owner_budget" in calls(name) and name != "_enforce_owner_budget"
    )
    assert owners == ["_execute_action", "game_prologue", "new_game"]


def test_quota_error_reaches_sse_payload_with_retry():
    assert "retry_after_seconds=exc.retry_after_seconds" in Path("api.py").read_text(
        encoding="utf-8"
    )


def test_quota_exceeded_http_body_and_header(env, monkeypatch):
    client, _identity, _runtime = env
    monkeypatch.setenv("RPG_DAILY_TURN_QUOTA", "1")

    @api.app.get("/game/_probe_quota")
    def _probe():
        api._enforce_owner_budget("llm_aux")
        return {"ok": True}

    api.app.router.routes.insert(0, api.app.router.routes.pop())  # antes do catch-all da SPA
    try:
        _as(client, "tok-a")
        assert client.get("/game/_probe_quota").status_code == 200
        out = client.get("/game/_probe_quota")
        assert out.status_code == 429
        assert out.json()["detail"] == "daily_quota_exceeded" and out.json()["scope"] == "daily"
        assert int(out.headers["Retry-After"]) == out.json()["retry_after_seconds"] >= 1
    finally:
        api.app.router.routes[:] = [
            r for r in api.app.router.routes if getattr(r, "path", "") != "/game/_probe_quota"
        ]


# --- R6: authfail --------------------------------------------------------------------------


def test_authfail_bucket_blocks_before_calling_the_verifier(env):
    client, identity, _rt = env
    _as(client, "garbage")
    statuses = [client.get("/game/state").status_code for _ in range(59)]
    assert set(statuses) == {401}
    assert client.get("/game/state").status_code == 401  # 60a ainda dentro do limite
    assert client.get("/game/state").status_code == 429  # 61a falha estoura
    calls = identity.calls
    out = client.get("/game/state")
    assert out.status_code == 429 and out.json()["scope"] == "authfail"
    assert identity.calls == calls  # bloqueado sem chamar o verificador


def test_authfail_is_per_ip(env, monkeypatch):
    client, _identity, _rt = env
    _as(client, "garbage")
    for _ in range(61):
        client.get("/game/state")
    monkeypatch.setenv("RPG_TRUSTED_PROXY_HOPS", "1")
    out = client.get("/game/state", headers={"x-forwarded-for": "198.51.100.77"})
    assert out.status_code == 401  # outro IP nao herda o bloqueio


def test_missing_cookie_does_not_consume_the_authfail_bucket(env):
    """Revisao Sol: visitante deslogado (sem cookie) nao enche o balde do IP compartilhado."""
    client, _identity, _rt = env
    for cookie in [c for c in client.cookies.jar if c.name == "rpg_access"]:
        client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
    assert {client.get("/game/state").status_code for _ in range(80)} == {401}
    _as(client, "tok-a")
    assert client.get("/game/state").status_code != 429


def test_export_and_delete_skip_daily_counters_before_migration():
    """Revisao Sol: codigo sobe antes da migration -> export/exclusao nao quebram."""
    from infrastructure import account_lifecycle as al

    class Db:
        def __init__(self, present):
            self.present, self.queries = present, []

        def execute(self, sql, params=()):
            self.queries.append(sql)
            reg = params[0] if params else ""
            return SimpleNamespace(fetchone=lambda: {"r": reg if self.present else None})

    absent = al._present_tables(Db(False), al.EXPORT_TABLES)
    assert "owner_daily_counters" not in absent and "games" in absent
    assert "owner_daily_counters" in al._present_tables(Db(True), al.PRIVATE_TABLES)
    db = Db(False)
    al._present_tables(db, ("games", "turns"))
    assert db.queries == []  # so tabelas opcionais custam consulta
