"""SPEC-192: latency/bundle/plan measurements of the deployed staging, written to evidence/measurements.json."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone, UTC

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h
from scripts.staging.preview_isolation import PROJECT_ID, TEAM_ID

_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*MB", re.I)


def bundle_mb_from_events(texts: list[str]) -> list[float]:
    """Sizes (MB) mentioned in build log lines about the function bundle."""
    out = []
    for t in texts:
        if re.search(r"bundle|function|lambda|size", t, re.I):
            out += [float(m.replace(",", ".")) for m in _SIZE.findall(t)]
    return out


def timed_get(c: httpx.Client, url: str, **kw) -> tuple[int | None, float]:
    t0 = time.perf_counter()
    try:
        r = c.get(url, **kw)
        return r.status_code, (time.perf_counter() - t0) * 1000
    except httpx.HTTPError:
        return None, (time.perf_counter() - t0) * 1000


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument(
        "--redeploy", action="store_true", help="vercel deploy --prod and time the first request"
    )
    a = ap.parse_args(argv)
    env = s192.load_env()
    vh = {"Authorization": f"Bearer {env['VERCEL_TOKEN']}"}
    out: dict = {"at": s192.now_iso(), "base": a.base}
    c = httpx.Client(timeout=90, transport=httpx.HTTPTransport(retries=3))
    if a.redeploy:
        t0 = time.monotonic()
        for _ in range(3):
            r = s192.vercel(["deploy", "--prod", "--yes"], env, timeout=1200)
            if r.returncode == 0:
                break
        out["redeploy"] = {"returncode": r.returncode, "seconds": round(time.monotonic() - t0)}
        time.sleep(2)
        st1, ms1 = timed_get(c, a.base + "/health")
        st2, ms2 = timed_get(c, a.base + "/health")
        out["cold_start"] = {
            "first_request_after_deploy_ms": round(ms1),
            "status": st1,
            "second_request_ms": round(ms2),
            "note": "first request imports langgraph/langchain",
        }
    warm = [timed_get(c, a.base + "/health")[1] for _ in range(30)]
    out["health_warm"] = s192.stats(warm)
    admin = s192.Admin(env)
    user = admin.create_user()
    try:
        r = s192.app_login(c, a.base, user)
        dbms = [timed_get(c, a.base + "/game/saves")[1] for _ in range(20)]
        out["db_route_game_saves_warm"] = {**s192.stats(dbms), "login_status": r.status_code}
        c.post(a.base + "/auth/logout", headers=_h(a.base, r.json().get("csrf_token")))
    finally:
        admin.delete_user(user["id"])
    secret = env["RPG_CRON_SECRET"]
    cron = {}
    for path in ("jobs", "account-deletions", "operations"):
        client_ms, server_s = [], []
        for _ in range(3):
            t0 = time.perf_counter()
            rr = c.post(
                f"{a.base}/internal/cron/{path}", headers={"Authorization": f"Bearer {secret}"}
            )
            client_ms.append((time.perf_counter() - t0) * 1000)
            server_s.append(rr.json().get("duration_s") if rr.status_code == 200 else None)
        cron[path] = {"client_ms": s192.stats(client_ms), "server_duration_s": server_s}
    out["cron_calls"] = cron
    try:
        e2e = json.loads((s192.EVIDENCE / "e2e_session.json").read_text(encoding="utf-8"))[
            "checks"
        ]["sse_turns"]
        out["sse_from_e2e"] = {"ttfb_ms": e2e["ttfb_ms"], "total_ms": e2e["total_ms"]}
    except (OSError, KeyError, ValueError):
        out["sse_from_e2e"] = None
    team = {"params": {"teamId": TEAM_ID}, "headers": vh, "timeout": 60}
    user_info = (
        httpx.get("https://api.vercel.com/v2/user", headers=vh, timeout=60).json().get("user", {})
    )
    proj = httpx.get(f"https://api.vercel.com/v9/projects/{PROJECT_ID}", **team).json()
    dep_id = next(
        (d["id"] for d in proj.get("latestDeployments", []) if d.get("target") == "production"),
        None,
    )
    dep = (
        httpx.get(f"https://api.vercel.com/v13/deployments/{dep_id}", **team).json()
        if dep_id
        else {}
    )
    events = (
        httpx.get(f"https://api.vercel.com/v3/deployments/{dep_id}/events", **team).json()
        if dep_id
        else []
    )
    texts = [
        e.get("text") or (e.get("payload") or {}).get("text") or ""
        for e in events
        if isinstance(e, dict)
    ]
    out["vercel"] = {
        "plan": (user_info.get("billing") or {}).get("plan"),
        "deployment": dep_id,
        "regions": dep.get("regions"),
        "function_max_duration_s": 300,
        "build_duration_s": round(
            (dep.get("buildingAt") and (dep.get("ready", 0) - dep["buildingAt"]) / 1000) or 0
        ),
        "bundle_mb_mentions": bundle_mb_from_events(texts)[-6:],
    }
    frm = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    u = httpx.get(
        "https://api.vercel.com/v1/usage",
        headers=vh,
        timeout=60,
        params={"teamId": TEAM_ID, "from": frm, "to": to},
    )
    out["vercel_usage_api"] = {
        "status": u.status_code,
        "body": s192.common.redact_text(u.text[:600]),
    }
    out["cost"] = {
        "vercel": "USD 0 (Hobby plan; free tier limits)",
        "supabase": "Free plan (project ref staging)",
        "paid_provider_calls": 0,
    }
    s192.evidence("measurements", out)
    print(json.dumps({k: out[k] for k in ("health_warm", "db_route_game_saves_warm") if k in out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
