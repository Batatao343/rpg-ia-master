"""SPEC-236 §6.2 (teto diario cross-day) em 2 dias reais de staging.

  snapshot  : dia-de-teto (UTC-3), gasto do dia que conta (BRL), estado dos switches do teto e audit recente
  spend     : usuario sintetico + jogo + N turnos reais (gasto barato do dia; usuario mantido ate o cleanup)
  cleanup   : apaga o usuario sintetico do spend (depois do trip)
  finops    : snapshot -> POST /internal/cron/finops (Bearer do cron) -> snapshot; grava o resumo daily_cap_*

Uso (veja docs/staging-wave-2026-10-17/spec236-s62-plano.md):
  uv run --frozen python -m scripts.staging.spec236_daily_cap snapshot --label restore_check
  uv run --frozen python -m scripts.staging.spec236_daily_cap finops --label day1_trip --expect-trip

Evidencia: docs/staging-wave-2026-10-17/evidence/spec236_s62_<label>.json (sem PII/segredos).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from uuid import uuid4

import httpx

from scripts.staging import common, s192

EVIDENCE = common.ROOT / "docs" / "staging-wave-2026-10-17" / "evidence"
CAP_KEYS = ("image_generation", "stt_fallback_expensive")
TZ = timezone(timedelta(hours=-3))  # RPG_DAILY_SPEND_TZ_OFFSET_HOURS default (America/Sao_Paulo, sem DST)


def snapshot(env: dict) -> dict:
    def q(conn):
        now = conn.execute("select now() as n").fetchone()["n"]
        since = now.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
        spend = conn.execute(
            "select coalesce(sum(cost_usd),0) usd, count(*) n from app.usage_events "
            "where created_at >= %s and created_at <= %s and counts_as_spend", (since, now)).fetchone()
        fx = conn.execute("select fx_usd_brl from app.pricing_versions order by created_at desc limit 1").fetchone()
        switches = {r["key"]: {"enabled": r["enabled"], "actor_id": r["actor_id"], "updated_at": r["updated_at"]}
                    for r in conn.execute("select key, enabled, actor_id, updated_at from app.kill_switches "
                                          "where key = any(%s)", (list(CAP_KEYS),)).fetchall()}
        audit = [dict(r) for r in conn.execute(
            "select key, previous_enabled, enabled, actor_id, reason, created_at from app.kill_switch_audit "
            "where key = any(%s) order by created_at desc limit 12", (list(CAP_KEYS),)).fetchall()]
        fxv = fx["fx_usd_brl"] if fx else 6
        return {"db_now": now, "cap_day": now.astimezone(TZ).date().isoformat(), "cap_day_start_utc": since,
                "spend_usd_counts_as_spend": spend["usd"], "spend_events": spend["n"],
                "fx_usd_brl": fxv, "spend_brl_estimate": round(float(spend["usd"]) * float(fxv), 4),
                # default = enabled (no row) for a never-touched switch
                "switches": {k: switches.get(k, {"enabled": True, "row": "absent (default on)"}) for k in CAP_KEYS},
                "audit_recent": audit}
    return s192.query(env, q)


def call_finops(base: str, env: dict) -> dict:
    r = httpx.post(f"{base}/internal/cron/finops", timeout=120,
                   headers={"Authorization": f"Bearer {env['RPG_CRON_SECRET']}", "Content-Type": "application/json"},
                   json={})
    body = r.json() if r.content else {}
    keep = {k: v for k, v in body.items() if k.startswith("daily_cap") or k in (
        "ok", "failed", "alert_kinds", "blocking_alerts", "switches_off", "report_version", "duration_s")}
    return {"status": r.status_code, "client_at": s192.now_iso(), "summary": keep}


SPEND_USER = common.ROOT / ".tmp" / "spec236" / "spend_user.json"


def spend(base: str, env: dict, turns: int) -> dict:
    """Gasto real e barato no dia-de-teto: usuario sintetico + jogo + N turnos SSE (DeepSeek/Jina).

    O usuario/jogo NAO e apagado aqui: apagar o jogo apaga (cascade) os usage_events do dia, e o gasto
    some do teto. Use ``cleanup`` depois do trip."""
    from scripts.staging import e2e_session as e2e
    admin = s192.Admin(env)
    user = admin.create_user()
    SPEND_USER.parent.mkdir(parents=True, exist_ok=True)
    SPEND_USER.write_text(json.dumps({"id": user["id"]}), encoding="utf-8")
    c = httpx.Client(timeout=60, transport=httpx.HTTPTransport(retries=3))
    r = s192.app_login(c, base, user)
    csrf = (r.json() if r.status_code == 200 else {}).get("csrf_token") or c.cookies.get("rpg_csrf") or ""
    origins = json.loads((common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
    body = {"name": "Spec236 Heroi", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
            "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())}
    r = c.post(f"{base}/game/new", headers=e2e._h(base, csrf), json=body, timeout=180)
    game_id = (r.json() if r.status_code == 200 else {}).get("game_id", "")
    res = [e2e.stream_turn(c, base, csrf, game_id, e2e.ACTIONS[i % len(e2e.ACTIONS)], str(uuid4()))
           for i in range(turns)] if game_id else []
    return {"login": r.status_code, "game_created": bool(game_id),
            "turns": [{"status": t["status"], "has_done": t["has_done"], "has_error": t["has_error"]} for t in res]}


def cleanup(env: dict) -> dict:
    if not SPEND_USER.exists():
        return {"user": "none"}
    uid = json.loads(SPEND_USER.read_text(encoding="utf-8"))["id"]
    # app.games has no FK to auth.users: delete the synthetic games first (like e2e_session does).
    games = s192.query(env, lambda conn: conn.execute(
        "delete from app.games where owner_id=%s", (uid,)).rowcount)
    status = s192.Admin(env).delete_user(uid)
    if status in (200, 204, 404):
        SPEND_USER.unlink()
    return {"games_deleted": games, "user_delete_status": status}


def health(base: str) -> dict:
    try:
        return httpx.get(f"{base}/health", timeout=30).json()
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "finops", "spend", "cleanup"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--turns", type=int, default=3, help="spend: turnos SSE")
    ap.add_argument("--expect-trip", action="store_true", help="finops: exige image_generation desligado pelo cap")
    ap.add_argument("--expect-cap-brl", help="finops: exige que o deploy esteja com este teto (ex.: 0.01)")
    a = ap.parse_args(argv)
    env = s192.load_env()
    out: dict = {"label": a.label, "health": health(a.base), "before": snapshot(env)}
    ok = True
    if a.cmd == "spend":
        out["spend"] = spend(a.base, env, a.turns)
        out["after"] = snapshot(env)
        ok &= out["spend"]["game_created"] and out["after"]["spend_usd_counts_as_spend"] > out["before"]["spend_usd_counts_as_spend"]
    if a.cmd == "cleanup":
        out["cleanup"] = cleanup(env)
    if a.cmd == "finops":
        out["finops"] = call_finops(a.base, env)
        out["after"] = snapshot(env)
        summ = out["finops"]["summary"]
        if a.expect_cap_brl is not None:
            ok &= str(summ.get("daily_cap_brl")) in (a.expect_cap_brl, str(float(a.expect_cap_brl)))
        if a.expect_trip:
            switched = set(filter(None, str(summ.get("daily_cap_switched_off", "")).split(",")))
            override = str(summ.get("daily_cap_manual_override", ""))
            ok &= (bool(summ.get("daily_cap_exceeded")) and "image_generation" in switched
                   and "image_generation" not in override
                   and out["after"]["switches"]["image_generation"]["enabled"] is False)
        ok &= out["finops"]["status"] == 200
    out["ok"] = bool(ok)
    path = common.write_evidence(f"spec236_s62_{a.label}", out, EVIDENCE / f"spec236_s62_{a.label}.json")
    brief = {"ok": out["ok"], "cap_day": out["before"]["cap_day"],
             "spend_brl": out["before"]["spend_brl_estimate"],
             "switches_before": {k: v["enabled"] for k, v in out["before"]["switches"].items()}}
    if a.cmd == "finops":
        brief["finops"] = out["finops"]["summary"]
        brief["switches_after"] = {k: v["enabled"] for k, v in out["after"]["switches"].items()}
    print(json.dumps(brief, default=str), "->", path)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
