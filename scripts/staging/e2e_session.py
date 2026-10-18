"""SPEC-192 gate 1: end-to-end web-client flow on the deployed staging (cookies/CSRF/captcha/SSE)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from uuid import uuid4

import httpx

from scripts.staging import s192

TURNS = 5
ACTIONS = ["Observo ao redor com cuidado.", "Examino o chão em busca de pistas.",
           "Converso com quem estiver por perto.", "Procuro algo útil nos arredores.", "Descanso um instante."]


def _h(base: str, csrf: str | None = None) -> dict:
    h = {"Origin": base, "Content-Type": "application/json"}
    if csrf:
        h["X-CSRF-Token"] = csrf
    return h


def summarize_stream(events: list[dict], status: int, ttfb_ms: float, total_ms: float) -> dict:
    state = next((e["data"] for e in reversed(events) if e["event"] == "state"), None)
    narr = "".join(e["data"].get("chunk", "") for e in events
                   if e["event"] == "narrative" and isinstance(e["data"], dict))
    return {"status": status, "ttfb_ms": round(ttfb_ms, 1), "total_ms": round(total_ms, 1),
            "sequence": s192.sequence_summary(events),
            "has_done": any(e["event"] == "narrative" and isinstance(e["data"], dict)
                            and e["data"].get("done") for e in events),
            "narration_chars": len(narr), "has_error": any(e["event"] == "error" for e in events),
            "turn_count": ((state or {}).get("world") or {}).get("turn_count"),
            "session_actions": ((state or {}).get("continuity") or {}).get("session_action_count"),
            "state": state is not None}


def stream_turn(c: httpx.Client, base: str, csrf: str, game_id: str, text: str, action_id: str) -> dict:
    t0 = time.perf_counter()
    first = None
    lines = []
    with c.stream("POST", f"{base}/game/action/stream", headers=_h(base, csrf),
                  json={"input_text": text, "game_id": game_id, "action_id": action_id}, timeout=180) as r:
        status = r.status_code
        for ln in r.iter_lines():
            if first is None and ln:
                first = (time.perf_counter() - t0) * 1000
            lines.append(ln)
    return summarize_stream(s192.parse_sse(lines + [""]), status, first or 0.0,
                            (time.perf_counter() - t0) * 1000)


def turns_ok(turns: list[dict], base_turn: int) -> bool:
    counts = [t["turn_count"] for t in turns]
    expect = [base_turn + i + 1 for i in range(len(turns))]
    return (all(t["status"] == 200 and t["has_done"] and t["state"] and not t["has_error"]
                and t["narration_chars"] > 0 for t in turns)
            and counts == expect and len(set(counts)) == len(turns))


def run(base: str, env: dict) -> dict:
    admin = s192.Admin(env)
    out: dict = {"base": base, "at": s192.now_iso(), "checks": {}}
    ck = out["checks"]
    user = admin.create_user()
    game_ids: list[str] = []
    c = httpx.Client(timeout=60, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
    try:
        mail = f"spec192-signup-{uuid4().hex[:8]}@example.invalid"
        pw = "Spec192-" + uuid4().hex
        r_no = c.post(f"{base}/auth/signup", headers=_h(base), json={"email": mail, "password": pw, "age_confirmed": True})
        r_ok = c.post(f"{base}/auth/signup", headers=_h(base),
                      json={"email": mail, "password": pw, "age_confirmed": True,
                            "captcha_token": s192.CAPTCHA_TEST})
        def gotrue_probe(token):
            body = {"email": f"spec192-probe-{uuid4().hex[:8]}@example.invalid", "password": pw}
            if token:
                body["gotrue_meta_security"] = {"captcha_token": token}
            rr = c.post(f"{admin.url}/auth/v1/signup", headers={"apikey": env["SUPABASE_PUBLISHABLE_KEY"]}, json=body)
            return {"status": rr.status_code, "error_code": (rr.json() if rr.content else {}).get("error_code")}
        probe_no, probe_dummy = gotrue_probe(None), gotrue_probe(s192.CAPTCHA_TEST)
        with s192.db(env) as conn:
            for row in conn.execute("select id from auth.users where email like 'spec192-probe-%%' or email=%s", (mail,)).fetchall():
                admin.delete_user(str(row["id"]))
        captcha_codes = {"captcha_failed", "captcha_verification_failed", "captcha_token_missing"}

        def is_captcha_error(p: dict) -> bool:
            return p["status"] >= 400 and (p["error_code"] in captcha_codes or "captcha" in str(p["error_code"]))
        # R-01: with the real Turnstile secret GoTrue must reject the dummy token too; with Cloudflare's
        # always-pass TEST secret it is accepted (then any later error is SMTP/quota, never captcha).
        ck["signup_captcha"] = {
            "app_no_token_status": r_no.status_code, "app_dummy_token_status": r_ok.status_code,
            "gotrue_no_token": probe_no, "gotrue_dummy_token": probe_dummy,
            "turnstile_real_secret": is_captcha_error(probe_dummy),
            # Since the auth-debug fix (15cfd6a) the app answers 403 captcha_invalid when GoTrue rejects the
            # token (real Turnstile secret); with the TEST secret the dummy token passes and the app answers
            # the generic 202 (anti-enumeration).
            "note": "real secret: dummy token -> 403 captcha_invalid; test secret: 202 generic",
            "ok": r_no.status_code >= 400 and is_captcha_error(probe_no) and (
                r_ok.status_code in (200, 202)
                or (r_ok.status_code == 403 and is_captcha_error(probe_dummy)))}
        r = c.get(f"{base}/auth/config")
        cfg = r.json()
        ck["auth_config"] = {"status": r.status_code, "captcha_mode": (cfg.get("captcha") or {}).get("mode"),
                             "required": cfg.get("required"), "authenticated": cfg.get("authenticated")}
        creds = {"email": user["email"], "password": user["password"], "captcha_token": s192.CAPTCHA_TEST}
        r_noorigin = c.post(f"{base}/auth/login", headers={"Content-Type": "application/json"}, json=creds)
        r_nocaptcha = c.post(f"{base}/auth/login", headers=_h(base),
                             json={"email": user["email"], "password": user["password"]})
        r_dummy = c.post(f"{base}/auth/login", headers=_h(base), json=creds)
        # Session through the email-confirmation link (the path a real user takes; no captcha by design).
        r = s192.app_login(c, base, user)
        login_body = r.json() if r.status_code == 200 else {}
        csrf = login_body.get("csrf_token") or c.cookies.get("rpg_csrf") or ""
        cookies_set = s192.cookie_flags(r.headers.get_list("set-cookie"))
        secret_cookie_vals = [v for k, v in c.cookies.items() if k in ("rpg_access", "rpg_refresh")]
        ck["login"] = {"status": r.status_code, "origin_missing_status": r_noorigin.status_code,
                       "captcha_missing_status": r_nocaptcha.status_code,
                       "dummy_captcha_status": r_dummy.status_code, "via": "verify_link",
                       "authenticated": login_body.get("authenticated"), "cookie_names": sorted(cookies_set),
                       "body_has_bearer": s192.json_has_bearer(login_body, secret_cookie_vals),
                       "ok": r.status_code == 200 and r_noorigin.status_code >= 400 and r_nocaptcha.status_code >= 400}
        live = {k: v for k, v in cookies_set.items() if not v["deleted"]}
        ck["cookie_flags"] = {
            "set_on_login": cookies_set,
            "note": "rpg_access is SameSite=Lax by design; rpg_csrf is JS-readable by design (double-submit); "
                    "rpg_deletion entry is a clearing Set-Cookie",
            "ok": bool(live) and all(v["secure"] and v["samesite"] in ("strict", "lax") for v in live.values())
            and all(v["httponly"] for k, v in live.items() if "csrf" not in k)
            and not any(v["httponly"] for k, v in live.items() if "csrf" in k)}
        r = c.post(f"{base}/game/action", headers={"Origin": base, "Content-Type": "application/json"},
                   json={"input_text": "x", "game_id": str(uuid4())})
        ck["csrf_enforced"] = {"status_without_header": r.status_code, "ok": r.status_code in (401, 403)}
        origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        body = {"name": "Spec192 Heroi", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
                "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())}
        t0 = time.perf_counter()
        r = c.post(f"{base}/game/new", headers=_h(base, csrf), json=body, timeout=180)
        gj = r.json() if r.status_code == 200 else {}
        game_id = gj.get("game_id", "")
        if game_id:
            game_ids.append(game_id)
        base_turn = (gj.get("world") or {}).get("turn_count", 0)
        ck["new_game"] = {"status": r.status_code, "ms": round((time.perf_counter() - t0) * 1000),
                          "simulated": gj.get("simulated"), "turn_count": base_turn,
                          "body_has_bearer": s192.json_has_bearer(gj, secret_cookie_vals),
                          "ok": r.status_code == 200 and bool(game_id)}
        if not game_id:
            raise RuntimeError(f"new game failed: {r.status_code} {r.text[:200]}; login={ck['login']}")
        turns, ids = [], []
        for i in range(TURNS):
            ids.append(str(uuid4()))
            turns.append(stream_turn(c, base, csrf, game_id, ACTIONS[i], ids[-1]))
        counts = [t["turn_count"] for t in turns]
        ck["sse_turns"] = {"turns": turns, "observed_turn_counts": counts,
                           "expected_turn_counts": [base_turn + i + 1 for i in range(TURNS)],
                           "ttfb_ms": s192.stats([t["ttfb_ms"] for t in turns]),
                           "total_ms": s192.stats([t["total_ms"] for t in turns]),
                           "ok": turns_ok(turns, base_turn)}
        retry = stream_turn(c, base, csrf, game_id, ACTIONS[-1], ids[-1])
        ck["retry_same_action_id"] = {"retry": retry, "ok": retry["status"] == 200 and retry["turn_count"] == counts[-1]}
        r = c.get(f"{base}/game/state", params={"game_id": game_id})
        st = r.json() if r.status_code == 200 else {}
        ck["state"] = {"status": r.status_code, "turn_count": (st.get("world") or {}).get("turn_count"),
                       "body_has_bearer": s192.json_has_bearer(st, secret_cookie_vals),
                       "ok": r.status_code == 200 and (st.get("world") or {}).get("turn_count") == base_turn + TURNS}
        r = c.post(f"{base}/auth/logout", headers=_h(base, csrf))
        cleared = s192.cookie_flags(r.headers.get_list("set-cookie"))
        r2 = c.get(f"{base}/game/state", params={"game_id": game_id})
        ck["logout"] = {"status": r.status_code, "cleared": sorted(k for k, v in cleared.items() if v["deleted"]),
                        "state_after_status": r2.status_code, "ok": r.status_code in (200, 204) and r2.status_code == 401}
    finally:
        cleanup: dict = {}
        try:
            with s192.db(env) as conn:
                for gid in game_ids:
                    cleanup["games_deleted"] = cleanup.get("games_deleted", 0) + conn.execute(
                        "delete from app.games where id::text=%s", (gid,)).rowcount
        except Exception as exc:  # noqa: BLE001
            cleanup["games_error"] = type(exc).__name__
        cleanup["user_delete_status"] = admin.delete_user(user["id"])
        out["cleanup"] = cleanup
    out["ok"] = all(v.get("ok", True) for v in ck.values())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env())
    s192.evidence("e2e_session", res)
    print(json.dumps({"ok": res["ok"], **{k: v.get("ok") for k, v in res["checks"].items()}, "cleanup": res["cleanup"]}))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
