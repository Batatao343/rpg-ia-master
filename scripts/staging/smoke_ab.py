"""A/B smoke against the remote staging project with two synthetic users.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY),
DATABASE_URL (transaction pooler 6543). Everything created is removed in `finally`.
Evidence: one boolean per check (+ status codes / latency); no secrets.
"""

from __future__ import annotations

import argparse
import base64
import math
import os
import secrets
import statistics
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping
from uuid import uuid4

import httpx

from scripts.staging import common

BUCKET = "rpg-dynamic"
CHECKS = ["rls", "storage", "pgvector", "wallet", "auth_captcha", "pooler"]


def aggregate(results: Mapping[str, Mapping[str, Any]]) -> dict:
    """ok = every check passed; pending_migration checks are reported but do not fail."""
    failed = sorted(k for k, v in results.items() if not v.get("ok") and not v.get("pending_migration"))
    pending = sorted(k for k, v in results.items() if v.get("pending_migration"))
    return {"ok": not failed and bool(results), "failed": failed, "pending_migration": pending}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1)], 2)


def latency_summary(samples: list[float], errors: int) -> dict:
    return {"n": len(samples), "errors": errors, "p50_ms": percentile(samples, 50),
            "p95_ms": percentile(samples, 95), "mean_ms": round(statistics.mean(samples), 2) if samples else 0.0}


class Ctx:
    def __init__(self, env: Mapping[str, str], client: httpx.Client | None = None):
        self.url = common.env_required("SUPABASE_URL", env).rstrip("/")
        self.service = common.env_required("SUPABASE_SERVICE_ROLE_KEY", env)
        self.anon = env.get("SUPABASE_PUBLISHABLE_KEY") or common.env_required("SUPABASE_ANON_KEY", env)
        self.dsn = common.env_required("DATABASE_URL", env)
        self.http = client or httpx.Client(timeout=30)
        self.users: dict[str, dict] = {}

    def admin_headers(self) -> dict:
        return {"apikey": self.service, "Authorization": f"Bearer {self.service}"}

    def user_headers(self, who: str) -> dict:
        return {"apikey": self.anon, "Authorization": f"Bearer {self.users[who]['jwt']}"}

    def create_user(self, who: str) -> None:
        email = f"spec191-{who}-{uuid4().hex[:10]}@example.com"
        password = secrets.token_urlsafe(24)
        r = self.http.post(f"{self.url}/auth/v1/admin/users", headers=self.admin_headers(),
                           json={"email": email, "password": password, "email_confirm": True})
        r.raise_for_status()
        uid = r.json()["id"]
        self.users[who] = {"id": uid, "email": email, "password": password}
        # Password grant via publishable key; may require a captcha token if CAPTCHA is on -> use admin-issued
        # session fallback (generate_link is not a JWT), so we report the failure instead of bypassing it.
        t = self.http.post(f"{self.url}/auth/v1/token?grant_type=password",
                           headers={"apikey": self.anon},
                           json={"email": email, "password": password,
                                 "gotrue_meta_security": {"captcha_token": os.getenv("RPG_STAGING_SMOKE_CAPTCHA_TOKEN", "")}})
        t.raise_for_status()
        self.users[who]["jwt"] = t.json()["access_token"]

    def cleanup_users(self) -> dict:
        out = {}
        for who, u in self.users.items():
            r = self.http.delete(f"{self.url}/auth/v1/admin/users/{u['id']}", headers=self.admin_headers())
            out[who] = r.status_code
        return out


def check_rls(ctx: Ctx) -> dict:
    import psycopg
    a, b = ctx.users["A"]["id"], ctx.users["B"]["id"]
    ga, gb = str(uuid4()), str(uuid4())
    res: dict[str, Any] = {"ok": False}
    with psycopg.connect(ctx.dsn, autocommit=True, prepare_threshold=None) as admin:
        try:
            admin.execute(
                """insert into app.games (id,owner_id,schema_version,state,state_sha256,status,player_name,
                   class_name,player_level,location_name,world_day,game_over,combat_simulation)
                   values (%s,%s,3,jsonb_build_object('game_id',%s::text),%s,'active','A','Devoto',1,'Teste',1,false,false),
                          (%s,%s,3,jsonb_build_object('game_id',%s::text),%s,'active','B','Devoto',1,'Teste',1,false,false)""",
                (ga, a, ga, "a" * 64, gb, b, gb, "b" * 64))
            res["rpg_api_bypassrls"] = admin.execute(
                "select rolbypassrls from pg_roles where rolname='rpg_api'").fetchone()[0]
            seen = {}
            for who, uid in (("A", a), ("B", b)):
                with admin.transaction():
                    admin.execute("set local role rpg_api")
                    admin.execute("select set_config('request.jwt.claim.sub', %s, true)", (uid,))
                    seen[who] = {str(r[0]) for r in admin.execute("select id from app.games").fetchall()}
            res.update(a_sees_only_own=seen["A"] == {ga}, b_sees_only_own=seen["B"] == {gb})
            try:
                with admin.transaction():
                    admin.execute("set local role rpg_api")
                    admin.execute("select set_config('request.jwt.claim.sub', %s, true)", (a,))
                    admin.execute("update app.games set owner_id=%s where id=%s", (b, ga))
                res["owner_reassign_blocked"] = False
            except psycopg.errors.InsufficientPrivilege:
                res["owner_reassign_blocked"] = True
            res["ok"] = bool(res["a_sees_only_own"] and res["b_sees_only_own"] and res["owner_reassign_blocked"]
                             and res["rpg_api_bypassrls"] is False)
        finally:
            admin.execute("delete from app.games where id in (%s,%s)", (ga, gb))
    return res


# 1x1 lossless WebP; the private bucket only accepts image/webp (migration 20260820113242).
_TINY_WEBP = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")


def check_storage(ctx: Ctx) -> dict:
    uid_a = ctx.users["A"]["id"]
    path = f"users/{uid_a}/spec191-{uuid4().hex[:8]}.webp"
    base = f"{ctx.url}/storage/v1/object"
    res: dict[str, Any] = {"ok": False}
    try:
        up = ctx.http.post(f"{base}/{BUCKET}/{path}", headers={**ctx.user_headers("A"), "Content-Type": "image/webp"},
                           content=_TINY_WEBP)
        res["a_upload_status"] = up.status_code
        res["a_reads_own"] = ctx.http.get(f"{base}/authenticated/{BUCKET}/{path}", headers=ctx.user_headers("A")).status_code == 200
        res["b_read_status"] = ctx.http.get(f"{base}/authenticated/{BUCKET}/{path}", headers=ctx.user_headers("B")).status_code
        res["anon_read_status"] = ctx.http.get(f"{base}/authenticated/{BUCKET}/{path}", headers={"apikey": ctx.anon}).status_code
        res["anon_public_status"] = ctx.http.get(f"{base}/public/{BUCKET}/{path}").status_code
        s = ctx.http.post(f"{base}/sign/{BUCKET}/{path}", headers=ctx.user_headers("A"), json={"expiresIn": 2})
        signed = f"{ctx.url}/storage/v1{s.json()['signedURL']}" if s.status_code == 200 else None
        res["signed_url_created"] = signed is not None
        if signed:
            res["signed_url_works"] = ctx.http.get(signed).status_code == 200
            time.sleep(4)
            res["signed_url_expired_status"] = ctx.http.get(signed).status_code
        res["ok"] = bool(up.status_code in (200, 201) and res["a_reads_own"]
                         and res["b_read_status"] >= 400 and res["anon_read_status"] >= 400
                         and res["anon_public_status"] >= 400 and res.get("signed_url_works")
                         and res.get("signed_url_expired_status", 200) >= 400)
    finally:
        res["cleanup_status"] = ctx.http.delete(f"{base}/{BUCKET}/{path}", headers=ctx.admin_headers()).status_code
    return res


def check_pgvector(ctx: Ctx) -> dict:
    from uuid import UUID
    from infrastructure.contracts import MemoryDocument, MemoryQuery, MemoryWriteIntent, Principal
    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from infrastructure.postgres import PostgresGameStore, PostgresPool
    pool = PostgresPool(ctx.dsn)
    pa = Principal(UUID(ctx.users["A"]["id"]), "supabase", ctx.users["A"]["id"])
    pb = Principal(UUID(ctx.users["B"]["id"]), "supabase", ctx.users["B"]["id"])
    gid = uuid4()
    state = {"game_id": str(gid), "messages": [], "event_log": [], "player": {}, "world": {}}
    store = PgVectorMemoryStore(pool, embedder=lambda _t: [1.0] + [0.0] * 1023)
    res: dict[str, Any] = {"ok": False}
    PostgresGameStore(pool).create(pa, state)
    try:
        store.stage(MemoryWriteIntent(MemoryDocument("spec191-mem", "A coroa rubra caiu no poco", "session",
                                                     {"visibility": "public", "commit_version": 1}),
                                      pa, gid, timeline_epoch=0))
        res["a_reads_own"] = [d.document_id for d in store.query(MemoryQuery("coroa", "session", pa, gid, k=3))] == ["spec191-mem"]
        res["b_reads_nothing"] = store.query(MemoryQuery("coroa", "session", pb, gid, k=3)) == []
        res["ok"] = bool(res["a_reads_own"] and res["b_reads_nothing"])
    finally:
        PostgresGameStore(pool).delete(pa, gid)
        pool.close()
    return res


SYNTH_PRICING = "spec191-smoke"
SYNTH_SKU = "spec191-smoke-sku"


def _seed_wallet_prereqs(dsn: str) -> None:
    """Idempotent synthetic pricing version + SKU (append-only ledger FKs; rows are retained by design)."""
    import psycopg
    from psycopg.types.json import Jsonb
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as c:
        c.execute(
            """insert into app.pricing_versions
            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,fx_max_age_seconds,
             fx_buffer_rate,rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
             rate_card_max_age_seconds,channel_fees)
            values (%s,0.03,5,'spec191 synthetic',now(),86400,0.10,%s,%s,'spec191 synthetic',%s,86400,%s)
            on conflict (version_id) do nothing""",
            (SYNTH_PRICING, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256, INSTALLED_RATE_CARD_OBSERVED_AT,
             Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
        c.execute(
            """insert into app.purchase_skus (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
            values (%s,%s,'web',%s,10.50,311) on conflict (sku_id) do nothing""",
            (SYNTH_SKU, SYNTH_PRICING, SYNTH_SKU))


def check_wallet(ctx: Ctx) -> dict:
    """A gets one real purchase entry through PostgresWallet; B must see nothing. wallet_* facts are
    append-only (immutable triggers), so the synthetic account + 1 entry of A are RETAINED (documented)."""
    from uuid import UUID
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet
    res: dict[str, Any] = {"ok": False}
    probe = ctx.http.post(f"{ctx.url}/rest/v1/rpc/rpg_wallet_balance", headers=ctx.user_headers("A"), json={})
    if probe.status_code == 404 or (probe.status_code >= 400 and "rpg_wallet_balance" in probe.text):
        return {"ok": False, "pending_migration": True, "a_status": probe.status_code}
    _seed_wallet_prereqs(ctx.dsn)
    uid_a = ctx.users["A"]["id"]
    pool = PostgresPool(ctx.dsn)
    try:
        PostgresWallet(pool).credit_verified_purchase(
            Principal(UUID(uid_a), "supabase", uid_a), channel="web", payment_id="spec191-" + uuid4().hex,
            sku_id=SYNTH_SKU, verified=True)
    finally:
        pool.close()
    res["seeded_entries_for_a"] = 1

    def call(who: str, fn: str, body: dict) -> list:
        r = ctx.http.post(f"{ctx.url}/rest/v1/rpc/{fn}", headers=ctx.user_headers(who), json=body)
        res[f"{who.lower()}_{fn}_status"] = r.status_code
        data = r.json() if r.status_code == 200 else []
        return data if isinstance(data, list) else [data]

    a_bal, b_bal = call("A", "rpg_wallet_balance", {}), call("B", "rpg_wallet_balance", {})
    a_his, b_his = call("A", "rpg_wallet_history", {"p_limit": 5}), call("B", "rpg_wallet_history", {})
    res["a_balance_rows"], res["b_balance_rows"] = len(a_bal), len(b_bal)
    res["a_history_rows"], res["b_history_rows"] = len(a_his), len(b_his)
    res["a_balance_is_own_and_311"] = (len(a_bal) == 1 and str(a_bal[0]["owner_id"]) == uid_a
                                       and a_bal[0]["available_milli"] == 311)
    res["a_history_only_own"] = len(a_his) == 1 and all(str(x["owner_id"]) == uid_a for x in a_his)
    res["anon_rpc_status"] = ctx.http.post(f"{ctx.url}/rest/v1/rpc/rpg_wallet_balance",
                                           headers={"apikey": ctx.anon}, json={}).status_code
    res["ok"] = bool(res["a_balance_is_own_and_311"] and res["a_history_only_own"] and not b_bal and not b_his
                     and res["anon_rpc_status"] >= 400)
    return res


def check_auth_captcha(ctx: Ctx) -> dict:
    """Direct GoTrue calls with publishable key and NO captcha token must be rejected (4xx captcha)."""
    email = f"spec191-captcha-{uuid4().hex[:8]}@example.com"
    h = {"apikey": ctx.anon}
    calls = {
        "signup": ("/auth/v1/signup", {"email": email, "password": secrets.token_urlsafe(18)}),
        "recover": ("/auth/v1/recover", {"email": email}),
        "resend": ("/auth/v1/resend", {"type": "signup", "email": email}),
    }
    res: dict[str, Any] = {}
    for name, (path, body) in calls.items():
        r = ctx.http.post(ctx.url + path, headers=h, json=body)
        text = r.text.lower()
        res[name] = {"status": r.status_code, "captcha_error": "captcha" in text}
    res["ok"] = all(v["status"] in (400, 401, 403, 422) and v["captcha_error"] for v in res.values())
    return res


POOLER_CONNECT_TIMEOUT = 3  # same as runtime hosted-supabase default (RPG_DB_CONNECT_TIMEOUT_SECONDS)
SLOW_CONNECT_MS = 1000.0


def pooler_attempt(dsn: str, connect_timeout: float = POOLER_CONNECT_TIMEOUT, hostaddr: str | None = None) -> dict:
    """One connect + `select 1`; records the peer address psycopg ended up on (after any failover)."""
    import psycopg
    t0 = time.perf_counter()
    kw: dict[str, Any] = {"autocommit": True, "prepare_threshold": None, "connect_timeout": int(connect_timeout)}
    if hostaddr:
        kw["hostaddr"] = hostaddr
    try:
        with psycopg.connect(dsn, **kw) as c:
            t1 = time.perf_counter()
            c.execute("select 1").fetchone()
            t2 = time.perf_counter()
            return {"connect": (t1 - t0) * 1000, "query": (t2 - t1) * 1000, "total": (t2 - t0) * 1000,
                    "ssl": bool(c.info.pgconn.ssl_in_use), "peer": c.info.hostaddr}
    except Exception as exc:  # noqa: BLE001
        return {"error": True, "error_type": type(exc).__name__, "total": (time.perf_counter() - t0) * 1000,
                "peer": hostaddr}


def pooler_stats(rows: list[dict], connect_timeout: float = POOLER_CONNECT_TIMEOUT) -> dict:
    """Aggregate attempts. A successful connect taking >= connect_timeout implies a failover to another IP."""
    ok = [r for r in rows if "error" not in r]
    out = latency_summary([r["total"] for r in ok], len(rows) - len(ok))
    out["connect"] = latency_summary([r["connect"] for r in ok], 0)
    out["query"] = latency_summary([r["query"] for r in ok], 0)
    out["max_total_ms"] = round(max((r["total"] for r in ok), default=0.0), 2)
    out["slow_connects"] = sum(1 for r in ok if r["connect"] > SLOW_CONNECT_MS)
    out["failovers"] = sum(1 for r in ok if r["connect"] >= connect_timeout * 1000)
    peers: dict[str, int] = {}
    for r in ok:
        peers[str(r.get("peer"))] = peers.get(str(r.get("peer")), 0) + 1
    out["peers"] = peers
    return out


def pooler_ok(stats: Mapping[str, Any], connect_timeout: float = POOLER_CONNECT_TIMEOUT) -> bool:
    """zero errors AND p95 total < 1000 ms AND max total < 2*connect_timeout+1s (one failover fits)."""
    return bool(stats["errors"] == 0 and stats["n"] > 0 and stats["p95_ms"] < 1000.0
                and stats["max_total_ms"] < (2 * connect_timeout + 1) * 1000)


def check_pooler(ctx: Ctx, n_seq: int = 50, n_conc: int = 10) -> dict:
    ct = POOLER_CONNECT_TIMEOUT
    seq = [pooler_attempt(ctx.dsn, ct) for _ in range(n_seq)]
    with ThreadPoolExecutor(n_conc) as ex:
        conc = list(ex.map(lambda _: pooler_attempt(ctx.dsn, ct), range(n_conc)))
    allrows = seq + conc
    allok = [r for r in allrows if "error" not in r]
    res: dict[str, Any] = {"sequential": pooler_stats(seq, ct), "concurrent": pooler_stats(conc, ct),
                           "overall": pooler_stats(allrows, ct), "n_sequential": n_seq,
                           "n_concurrent": n_conc, "connect_timeout_s": ct,
                           "ssl_in_use_all": bool(allok) and all(r["ssl"] for r in allok)}
    res["ok"] = pooler_ok(res["overall"], ct) and res["ssl_in_use_all"]
    return res


def pooler_per_ip(dsn: str, n: int = 25, connect_timeout: float = 5) -> dict:
    """Diagnostic: probe every resolved IPv4 of the pooler host n times with hostaddr (same TLS name)."""
    import socket
    from urllib.parse import urlsplit
    u = urlsplit(dsn)
    host, port = u.hostname or "", u.port or 5432
    ips = sorted({ai[4][0] for ai in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)})
    out: dict[str, Any] = {"host": host, "port": port, "n_per_ip": n, "connect_timeout_s": connect_timeout, "ips": {}}
    for ip in ips:
        rows = [pooler_attempt(dsn, connect_timeout, hostaddr=ip) for _ in range(n)]
        out["ips"][ip] = per_ip_summary(rows, connect_timeout)
    out["ok"] = all(v["timeout_rate"] == 0 and v["errors"] == 0 for v in out["ips"].values())
    return out


def per_ip_summary(rows: list[dict], connect_timeout: float) -> dict:
    bad = [r for r in rows if "error" in r]
    # a failed attempt that burned ~the whole connect_timeout is a handshake stall (timeout)
    timeouts = [r for r in bad if r["total"] >= connect_timeout * 1000 * 0.9]
    good = [r["total"] for r in rows if "error" not in r]
    return {"n": len(rows), "errors": len(bad), "timeouts": len(timeouts),
            "timeout_rate": round(len(timeouts) / len(rows), 3) if rows else 0.0,
            "error_types": sorted({r["error_type"] for r in bad}),
            "ok_p50_ms": percentile(good, 50), "ok_p95_ms": percentile(good, 95),
            "ok_max_ms": round(max(good, default=0.0), 2)}


CHECK_FUNCS: dict[str, Callable[[Ctx], dict]] = {
    "rls": check_rls, "storage": check_storage, "pgvector": check_pgvector, "wallet": check_wallet,
    "auth_captcha": check_auth_captcha, "pooler": check_pooler,
}


def run(ctx: Ctx, only: list[str] | None = None) -> dict:
    results: dict[str, dict] = {}
    cleanup: dict[str, Any] = {}
    try:
        # captcha check needs no users; the others need A/B
        for who in ("A", "B"):
            try:
                ctx.create_user(who)
            except Exception as exc:  # noqa: BLE001
                results["setup_users"] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200]}
                break
        for name in only or CHECKS:
            if "setup_users" in results and name not in ("auth_captcha", "pooler"):
                continue
            try:
                results[name] = CHECK_FUNCS[name](ctx)
            except Exception as exc:  # noqa: BLE001
                results[name] = {"ok": False, "error": type(exc).__name__ + ": " + str(exc)[:200],
                                 "trace": traceback.format_exc(limit=2)[-400:]}
    finally:
        cleanup["users_delete_status"] = ctx.cleanup_users()
    return {"checks": results, "summary": aggregate(results), "cleanup": cleanup}


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Remote staging A/B smoke")
    common.add_guard_args(p)
    p.add_argument("--only", nargs="*", choices=CHECKS)
    p.add_argument("--out")
    p.add_argument("--per-ip", action="store_true", help="diagnostic: probe each resolved pooler IP N times")
    p.add_argument("--n", type=int, default=25)
    a = p.parse_args(argv)
    ref = common.require_staging(a.confirm_staging)
    if a.per_ip:
        dsn = common.env_required("DATABASE_URL", os.environ)
        common.assert_ref_in(ref, DATABASE_URL=dsn)
        result = {"project_ref": ref, **pooler_per_ip(dsn, a.n)}
        print(common.write_evidence("pooler_per_ip", result, a.out))
        return 0
    ctx = Ctx(os.environ)
    common.assert_ref_in(ref, SUPABASE_URL=ctx.url, DATABASE_URL=ctx.dsn)
    result = {"project_ref": ref, **run(ctx, a.only)}
    print(common.write_evidence("smoke_ab", result, a.out))
    return 0 if result["summary"]["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
