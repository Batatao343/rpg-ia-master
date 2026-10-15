"""SPEC-197 R5: incident / rollback drill on the deployed staging, with measured times.

kill-switch : flips ``image_generation`` OFF with scripts/admin_kill_switch.py against the staging DB, polls
              the real endpoint until /game/{id}/art/quote answers 503 image_generation_disabled (state stays
              readable), flips it back ON and polls until the quote works again. No provider is called.
rollback    : ``vercel rollback <url>`` to a previous production deployment, waits until the alias serves the old
              ``git_sha``, then ``vercel promote <url>`` back to the current one and waits again.
Both write timings (seconds) to docs/spec197/evidence/incident_drill.json. Deployment URLs are not secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.two_user_smoke import User

OUT = s192.common.ROOT / "docs" / "spec197" / "evidence" / "incident_drill.json"
ACTOR = "drill-spec197"


def _switch(action: str, reason: str) -> tuple[int, float]:
    t0 = time.perf_counter()
    r = subprocess.run([sys.executable, "scripts/admin_kill_switch.py", "--dsn-env", "RPG_STAGING_DB_URL",
                        "--env-file", ".env.staging", action, "image_generation", "--actor", ACTOR,
                        "--reason", reason, "--apply"], cwd=s192.common.ROOT, capture_output=True, text=True)
    return r.returncode, time.perf_counter() - t0


def _poll(fn, want, timeout=90.0, step=1.0) -> tuple[bool, float, list]:
    t0, seen = time.perf_counter(), []
    while time.perf_counter() - t0 < timeout:
        got = fn()
        seen.append(got)
        if want(got):
            return True, time.perf_counter() - t0, seen[-3:]
        time.sleep(step)
    return False, time.perf_counter() - t0, seen[-3:]


def kill_switch(base: str, env: dict[str, str]) -> dict:
    admin = s192.Admin(env)
    u = User(base, admin, "D")
    res: dict = {"switch": "image_generation"}
    try:
        u.login()
        u.new_game()

        def quote():
            r = u.post(f"/game/{u.game_id}/art/quote", {"image_type": "player"})
            return r.status_code, (r.json().get("detail") if r.status_code >= 400 and r.content else None)

        def state():
            return u.get("/game/state", params={"game_id": u.game_id}).status_code
        res["baseline"] = {"quote": quote(), "state": state()}
        rc, off_s = _switch("off", "SPEC-197 incident drill (staging)")
        ok, prop_s, seen = _poll(quote, lambda g: g[0] == 503 and g[1] == "image_generation_disabled")
        res["off"] = {"cli_returncode": rc, "cli_seconds": round(off_s, 2), "propagation_seconds": round(prop_s, 2),
                      "reached_503_image_generation_disabled": ok, "last_seen": seen,
                      "state_readable_while_off": state() == 200,
                      "total_seconds_from_cli_start": round(off_s + prop_s, 2)}
        rc, on_s = _switch("on", "SPEC-197 incident drill reset (staging)")
        ok2, prop2, seen2 = _poll(quote, lambda g: g[0] == 200)
        res["on"] = {"cli_returncode": rc, "cli_seconds": round(on_s, 2), "propagation_seconds": round(prop2, 2),
                     "quote_restored": ok2, "last_seen": seen2}
        audit = subprocess.run([sys.executable, "scripts/admin_kill_switch.py", "--dsn-env", "RPG_STAGING_DB_URL",
                                "--env-file", ".env.staging", "audit", "--limit", "4"],
                               cwd=s192.common.ROOT, capture_output=True, text=True).stdout
        res["audit_has_drill_actor"] = ACTOR in audit
        res["ok"] = bool(res["baseline"]["quote"][0] == 200 and res["off"]["reached_503_image_generation_disabled"]
                         and res["off"]["state_readable_while_off"] and res["on"]["quote_restored"]
                         and res["audit_has_drill_actor"])
    finally:
        s192.query(env, lambda c: c.execute("delete from app.games where id::text=%s", (u.game_id,)) if u.game_id else None)
        res["cleanup_user_status"] = admin.delete_user(u.id)
        if not res.get("on"):  # never leave the switch off after a failed drill
            _switch("on", "SPEC-197 drill failure reset")
    return res


def _sha(base: str) -> str:
    try:
        return httpx.get(f"{base}/health", timeout=15).json().get("git_sha", "")
    except Exception:  # noqa: BLE001
        return "?"


def rollback(base: str, env: dict[str, str], previous_url: str, current_url: str, previous_sha: str, current_sha: str) -> dict:
    res: dict = {"previous_url": previous_url, "current_url": current_url, "sha_before": _sha(base)}
    r, ms = s192.timed(lambda: s192.vercel(["rollback", previous_url, "--yes"], env, timeout=300))
    res["rollback_command"] = {"returncode": r.returncode, "cli_seconds": round(ms / 1000, 2),
                               "output": (r.stdout + r.stderr).encode("ascii", "replace").decode()[-300:]}
    ok, s, seen = _poll(lambda: _sha(base), lambda g: g == previous_sha, timeout=120)
    res["rollback_serving_previous_sha"] = {"ok": ok, "seconds_after_cli": round(s, 2), "last_seen": seen}
    res["health_while_rolled_back"] = {"git_sha": _sha(base)}
    r2, ms2 = s192.timed(lambda: s192.vercel(["promote", current_url, "--yes"], env, timeout=300))
    res["promote_command"] = {"returncode": r2.returncode, "cli_seconds": round(ms2 / 1000, 2),
                              "output": (r2.stdout + r2.stderr).encode("ascii", "replace").decode()[-300:]}
    ok2, s2, seen2 = _poll(lambda: _sha(base), lambda g: g == current_sha, timeout=120)
    res["promote_serving_current_sha"] = {"ok": ok2, "seconds_after_cli": round(s2, 2), "last_seen": seen2}
    res["total_rollback_cycle_seconds"] = round((ms + ms2) / 1000 + s + s2, 2)
    res["ok"] = bool(r.returncode == 0 and r2.returncode == 0 and ok and ok2)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["kill-switch", "rollback"])
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--previous-url")
    ap.add_argument("--current-url")
    ap.add_argument("--previous-sha")
    ap.add_argument("--current-sha")
    a = ap.parse_args(argv)
    env = s192.load_env()
    prior = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if a.part == "kill-switch":
        prior["kill_switch"] = kill_switch(a.base, env)
    else:
        prior["vercel_rollback"] = rollback(a.base, env, a.previous_url, a.current_url, a.previous_sha, a.current_sha)
    prior["at"] = s192.now_iso()
    prior["ok"] = all(v.get("ok") for k, v in prior.items() if isinstance(v, dict))
    print(s192.common.write_evidence("incident_drill", prior, str(OUT)))
    return 0 if prior["ok"] else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())
