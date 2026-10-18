"""Staging smoke for the 2026-10-17 security/finops wave (SPEC-219/220/222/224/236).

Real LLM on staging: keeps the turn count to what the checks need (21 + 1 + 1 turns).
Evidence holds only names, statuses, counts and pseudonyms (no secrets, no player text).

* SPEC-220: "Sair" without a live access cookie still revokes the refresh (old refresh -> 401);
  11 wrong passwords -> 429.
* SPEC-219: owner A 21 turns/min -> 429 on the 21st with Retry-After; owner B on the same IP
  plays; invalid access token rejected without an Auth round trip (log check is manual/MCP);
  /game/chronicle/search 11th/min -> 429; R5: the IP bucket key equals the pseudonym of the
  caller's public IP (client_ip = x-vercel-forwarded-for).
* SPEC-222: one turn carries a sentinel (checked in function logs afterwards); /account/export
  lists the new tables and no purchase token.
* SPEC-236: failed attempts in usage_events are zero-cost facts outside spend.
"""
from __future__ import annotations

import argparse
import os
import secrets
import time
from decimal import Decimal
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.two_user_smoke import User


def _turn(u: User, text: str) -> httpx.Response:
    return u.post("/game/action", {"input_text": text, "game_id": u.game_id, "action_id": str(uuid4())},
                  timeout=180)


def _auth220(base: str, admin, users: list, ck: dict) -> None:
    """SPEC-220. The login budget per IP is 20/15 min: run it apart from the turn part."""
    lo = User(base, admin, "L"); users.append(lo)
    login = lo.login()
    old_refresh = lo.c.cookies.get("rpg_refresh", path="/auth/refresh") or lo.c.cookies.get("rpg_refresh")
    lo.c.cookies.delete("rpg_access")
    out_status = lo.post("/auth/refresh/logout").status_code
    replay = httpx.Client(timeout=60)
    replay.cookies.set("rpg_refresh", old_refresh or "", domain=httpx.URL(base).host, path="/auth/refresh")
    replay.cookies.set("rpg_csrf", lo.csrf, domain=httpx.URL(base).host, path="/")
    refreshed = replay.post(f"{base}/auth/refresh", headers={"Origin": base, "X-CSRF-Token": lo.csrf}).status_code
    ck["spec220_logout_revokes_refresh"] = {
        "login": login, "had_refresh_cookie": bool(old_refresh), "logout": out_status,
        "refresh_with_old_token": refreshed, "ok": login == 200 and bool(old_refresh)
        and out_status == 204 and refreshed == 401}

    # --- SPEC-220: lockout after wrong passwords ------------------------------------------
    lk = User(base, admin, "K"); users.append(lk)
    codes = []
    for _ in range(11):
        r = lk.c.post(f"{base}/auth/login", headers={"Origin": base}, json={
            "email": lk.info["email"], "password": "wrong-password-xx", "captcha_token": s192.CAPTCHA_TEST})
        codes.append(r.status_code)
    ck["spec220_lockout"] = {"codes": codes, "retry_after": r.headers.get("Retry-After"),
                             "ok": codes[-1] == 429 and all(c in (400, 401, 429) for c in codes)}


def run(base: str, env: dict[str, str], *, auth220: bool = True) -> dict:
    from observability.telemetry import pseudonym
    admin = s192.Admin(env)
    secret = env.get("RPG_TELEMETRY_SECRET", "")
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    out["deployed_git_sha"] = httpx.get(f"{base}/health", timeout=30).json().get("git_sha")
    public_ip = httpx.get("https://api.ipify.org", timeout=30).text.strip()
    ip_ref = pseudonym(public_ip, secret=secret)
    out["caller_ip_pseudonym"] = ip_ref
    sentinel = "SENTINELA" + secrets.token_hex(6).upper()
    out["sentinel"] = sentinel  # random marker, not player data; grep it in the function logs
    users: list[User] = []
    try:
        if auth220:
            _auth220(base, admin, users, ck)

        # --- SPEC-219: owner minute budget on turns + sentinel turn ---------------------------
        a = User(base, admin, "A"); users.append(a)
        b = User(base, admin, "B"); users.append(b)
        ck["logins"] = {"a": a.login(), "b": b.login()}
        ck["logins"]["ok"] = ck["logins"]["a"] == 200 and ck["logins"]["b"] == 200
        new_a, new_b = a.new_game(), b.new_game()
        codes, retry_after, started = [], None, time.monotonic()
        for i in range(21):
            text = f"Observo ao redor com cuidado. {sentinel}" if i == 0 else "Espero."
            r = _turn(a, text)
            codes.append(r.status_code)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                body = r.json()
                break
        elapsed = round(time.monotonic() - started, 1)
        ck["spec219_owner_turn_minute"] = {
            "new_game": new_a, "codes": codes, "elapsed_s": elapsed, "retry_after": retry_after,
            "body": body if codes[-1] == 429 else None,
            "ok": len(codes) == 21 and codes[-1] == 429 and all(c == 200 for c in codes[:-1])
            and bool(retry_after)}
        rb = _turn(b, "Observo ao redor.")
        ck["spec219_other_owner_same_ip"] = {"new_game": new_b, "status": rb.status_code, "ok": rb.status_code == 200}

        # invalid access token: 401, rejected locally (Auth log check is done separately)
        bad = httpx.Client(timeout=30)
        bad.cookies.set("rpg_access", "not-a-jwt-" + secrets.token_hex(8), domain=httpx.URL(base).host, path="/")
        st = bad.get(f"{base}/game/saves").status_code
        ck["spec219_invalid_token"] = {"status": st, "ok": st == 401}

        # chronicle search: embedding class 10/min per owner
        codes = []
        for _ in range(11):
            r = b.post("/game/chronicle/search", {"game_id": b.game_id, "query": "taverna"}, timeout=60)
            codes.append(r.status_code)
        ck["spec219_chronicle_search"] = {"codes": codes, "retry_after": r.headers.get("Retry-After"),
                                          "ok": codes[-1] == 429 and 429 not in codes[:-1]}

        # --- SPEC-222: export with the new tables, no purchase token --------------------------
        ra = b.post("/auth/reauth", {"password": b.info["password"], "captcha_token": s192.smoke_captcha()})
        ex = b.get("/account/export", timeout=120)
        body = ex.json() if ex.status_code == 200 else {}
        tables = sorted((body.get("tables") or body.get("data") or {}).keys()) if isinstance(body, dict) else []
        raw = ex.text if ex.status_code == 200 else ""
        ck["spec222_export"] = {"reauth": ra.status_code, "status": ex.status_code, "tables": tables,
                                "has_owner_daily_counters": "owner_daily_counters" in raw,
                                "purchase_token_key_present": '"purchase_token"' in raw,
                                "ok": ex.status_code == 200 and '"purchase_token"' not in raw}

        # --- DB-side checks (system DSN, read-only) -------------------------------------------
        with s192.db(env) as conn:
            usage = conn.execute(
                """select outcome, cost_basis, counts_as_spend, count(*) n, coalesce(sum(cost_usd),0)::text cost
                   from app.usage_events where owner_id = %s group by 1,2,3 order by 1""", (a.id,)).fetchall()
            daily = conn.execute("select class, count from app.owner_daily_counters where owner_id = %s",
                                 (a.id,)).fetchall()
            buckets = conn.execute(
                "select bucket_key from app.rate_limit_buckets where bucket_key like %s",
                (f"ip:{ip_ref}:%",)).fetchall()
        ck["spec236_usage_facts"] = {
            "rows": [dict(r) for r in usage],
            # every non-spend fact is zero-cost; at least one fact exists for the 20 turns
            "ok": bool(usage) and all(r["counts_as_spend"] or Decimal(r["cost"]) == 0 for r in usage)}
        ck["spec219_daily_counter"] = {"rows": [dict(r) for r in daily],
                                       "ok": any(r["class"] == "turn" and r["count"] >= 20 for r in daily)}
        ck["spec219_r5_ip_bucket"] = {"bucket_classes": sorted(r["bucket_key"].split(":")[-1] for r in buckets),
                                      "ok": bool(buckets)}
    finally:
        cleanup = {}
        try:
            with s192.db(env) as conn:
                for u in users:
                    if u.game_id:
                        cleanup[f"game_{u.label}"] = conn.execute(
                            "delete from app.games where id::text=%s", (u.game_id,)).rowcount
        except Exception as exc:  # noqa: BLE001
            cleanup["games_error"] = type(exc).__name__
        cleanup["users"] = {u.label: admin.delete_user(u.id) for u in users}
        out["cleanup"] = cleanup
    out["ok"] = all(v.get("ok", True) for v in ck.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-auth220", action="store_true")
    a = ap.parse_args(argv)
    env = s192.load_env()
    env.setdefault("RPG_TELEMETRY_SECRET", os.getenv("RPG_TELEMETRY_SECRET", ""))
    res = run(a.base, env, auth220=not a.skip_auth220)
    print(s192.common.write_evidence("security_wave_smoke", res, a.out))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
