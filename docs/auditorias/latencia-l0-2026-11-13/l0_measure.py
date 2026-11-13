"""L0 (auditoria de latencia 12/11): medicao decomposta do staging. So tempos/contagens, sem texto nem ids.

Uso (raiz do repo): bash scripts/dev/py.sh <este arquivo> --out <json> [--sessions 4] [--think 6]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from uuid import uuid4

sys.path.insert(0, os.getcwd())

import httpx  # noqa: E402

from scripts.staging import s192  # noqa: E402
from scripts.staging.e2e_session import _h  # noqa: E402
from scripts.staging.preview_isolation import PROJECT_ID, TEAM_ID  # noqa: E402
from scripts.staging.projection_measure import stream_turn  # noqa: E402

SCRIPT = [
    ("cena", "Observo ao redor com cuidado."),
    ("npc_novo", "Procuro a pessoa mais próxima e pergunto o que tem acontecido por aqui."),
    ("conversa", "Pergunto a essa mesma pessoa o nome dela e há quanto tempo vive aqui."),
    ("conversa", "Pergunto a ela quais são os perigos da região."),
    ("cena", "Examino o chão e os cantos em busca de algo útil."),
    ("npc_novo", "Procuro um mercador e pergunto o que ele vende."),
    ("conversa", "Pergunto ao mercador sobre rumores recentes."),
    ("conversa", "Pergunto ao mercador se ele conhece alguém que precise de ajuda."),
    ("cena", "Sigo pela rua principal observando as pessoas."),
    ("descanso", "Descanso até o amanhecer do dia seguinte."),
    ("cena", "Reviso meu equipamento e sigo em frente."),
    ("viagem", "Viajo para {dest}."),
    ("cena", "Observo o lugar onde cheguei."),
    ("descanso", "Monto acampamento e durmo até o dia seguinte."),
    ("combate", "Ataco a criatura hostil mais próxima."),
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _timed(fn) -> tuple[object, float]:
    t0 = time.perf_counter()
    r = fn()
    return r, round((time.perf_counter() - t0) * 1000, 1)


def _stats(values: list) -> dict:
    v = sorted(x for x in values if isinstance(x, (int, float)))
    if not v:
        return {"n": 0}
    return {
        "n": len(v),
        "p50": round(
            v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 1
        ),
        "p95": s192.pct(v, 95),
        "min": round(v[0], 1),
        "max": round(v[-1], 1),
    }


def _db_extract(env: dict, game_id: str) -> dict:
    from services.audit_trace import expand_trace

    def fn(conn):
        doc = conn.execute(
            "select version, state, pg_column_size(state) as stored_bytes, "
            "octet_length(state::text) as text_bytes from app.games where id::text=%s",
            (game_id,),
        ).fetchone()
        ev = conn.execute(
            "select count(*) as n from app.game_events where game_id::text=%s", (game_id,)
        ).fetchone()
        return doc, ev

    doc, ev = s192.query(env, fn)
    st = (doc or {}).get("state") or {}
    trace = expand_trace(st.get("audit_trace") or [])
    return {
        "version": (doc or {}).get("version"),
        "state_stored_bytes": (doc or {}).get("stored_bytes"),
        "state_text_bytes": (doc or {}).get("text_bytes"),
        "event_log_len": len(st.get("event_log") or []),
        "game_events_rows": (ev or {}).get("n"),
        "timing": [
            {
                "turn": t.get("turn"),
                **{
                    k: (t.get("timing") or {}).get(k)
                    for k in (
                        "phase_ms",
                        "ack_server_ms",
                        "ttfmc_server_ms",
                        "ttlt_server_ms",
                        "llm_attempts",
                        "llm_fallbacks",
                        "llm_failed_attempts",
                        "providers_used",
                    )
                },
            }
            for t in trace
        ],
    }


def session(base: str, env: dict, idx: int, think: float, origins: dict) -> dict:
    admin = s192.Admin(env)
    user = admin.create_user()
    out: dict = {"session": idx, "turns": []}
    game_id = ""
    c = httpx.Client(timeout=60, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
    try:
        r = s192.app_login(c, base, user)
        csrf = (
            (r.json() if r.status_code == 200 else {}).get("csrf_token")
            or c.cookies.get("rpg_csrf")
            or ""
        )
        regions = [x["name"] for x in origins["regions"]]
        region = regions[idx % len(regions)]
        dest = regions[(idx + 1) % len(regions)]
        char = {
            "name": "Medida Latencia",
            "race": origins["races"][idx % len(origins["races"])]["name"],
            "class_name": "Devoto do Abismo",
            "region": region,
            "level": 1,
            "backstory": "Cresci numa vila de pescadores e saí de casa atrás de um irmão desaparecido.",
        }
        # Abertura: prologo (1 SMART) + /game/new com o cenario aprovado (fluxo do cliente).
        t_start = _now_ms()
        pr, pr_ms = _timed(
            lambda: c.post(f"{base}/game/prologue", headers=_h(base, csrf), json=char, timeout=180)
        )
        pj = pr.json() if pr.status_code == 200 else {}
        body = {**char, "action_id": str(uuid4())}
        if pj.get("scenario"):
            body["scenario"] = pj["scenario"]
            if pj.get("scenario_token"):
                body["scenario_token"] = pj["scenario_token"]
        ng, ng_ms = _timed(
            lambda: c.post(f"{base}/game/new", headers=_h(base, csrf), json=body, timeout=240)
        )
        gj = ng.json() if ng.status_code == 200 else {}
        game_id = gj.get("game_id", "")
        out["opening"] = {
            "start_ms": t_start,
            "end_ms": _now_ms(),
            "prologue_status": pr.status_code,
            "prologue_ms": pr_ms,
            "prologue_mock": pj.get("mock"),
            "new_status": ng.status_code,
            "new_ms": ng_ms,
            "simulated": gj.get("simulated"),
            "with_scenario": "scenario" in body,
        }
        if not game_id:
            return out
        last_action = ""
        for i, (cat, text) in enumerate(SCRIPT):
            action_id = str(uuid4())
            # igual ao cliente: consulta da operacao ANTES do envio (operacao nova -> 404/pending)
            pre, pre_ms = _timed(lambda: c.get(f"{base}/game/{game_id}/operations/{action_id}"))
            start = _now_ms()
            row = stream_turn(c, base, csrf, game_id, text.format(dest=dest))
            end = _now_ms()
            last_action = action_id
            out["turns"].append(
                {
                    "i": i,
                    "category": cat,
                    "start_ms": start,
                    "end_ms": end,
                    "pre_get_operation_ms": pre_ms,
                    "pre_get_operation_status": pre.status_code,
                    **{
                        k: row.get(k)
                        for k in (
                            "status",
                            "ack",
                            "first_chunk",
                            "done",
                            "state",
                            "close",
                            "narration_chars",
                            "has_error",
                            "turn_count",
                        )
                    },
                }
            )
            if row["status"] == 503:
                out["aborted"] = "503"
                break
            time.sleep(think)
        # idas leves, servidor quente, mesma sessao autenticada
        out["warm"] = {
            "health": _stats([_timed(lambda: c.get(f"{base}/health"))[1] for _ in range(15)]),
            "game_saves": _stats(
                [_timed(lambda: c.get(f"{base}/game/saves"))[1] for _ in range(15)]
            ),
            "get_operation_unknown": _stats(
                [
                    _timed(lambda: c.get(f"{base}/game/{game_id}/operations/{uuid4()}"))[1]
                    for _ in range(15)
                ]
            ),
            "game_state": _stats(
                [
                    _timed(lambda: c.get(f"{base}/game/state", params={"game_id": game_id}))[1]
                    for _ in range(8)
                ]
            ),
        }
        _ = last_action
        out["db"] = _db_extract(env, game_id)
    finally:
        cleanup: dict = {}
        if game_id:
            try:
                cleanup["games_deleted"] = s192.query(
                    env,
                    lambda conn: (
                        conn.execute("delete from app.games where id::text=%s", (game_id,)).rowcount
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                cleanup["games_error"] = type(exc).__name__
        cleanup["user_delete_status"] = admin.delete_user(user["id"])
        out["cleanup"] = cleanup
        c.close()
    return out


def fetch_logs(env: dict, since: str, query: str) -> list[dict]:
    res = s192.vercel(
        [
            "logs",
            "--environment",
            "production",
            "--since",
            since,
            "--query",
            query,
            "--limit",
            "1000",
            "--json",
        ],
        env,
        timeout=300,
    )
    rows, seen = [], set()
    for line in (res.stdout or "").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        data = item.get("data", item) if isinstance(item, dict) else {}
        msg = str(data.get("message") or "")
        a = msg.find("{")
        if a < 0:
            continue
        try:
            payload = json.loads(msg[a:])
        except ValueError:
            continue
        ts = data.get("timestamp") or item.get("timestamp")
        if not isinstance(ts, (int, float)):
            from scripts.staging.jev_shadow_measure import _iso_ms

            ts = _iso_ms(str(ts or ""))
        key = (int(ts), json.dumps(payload, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        payload["ts"] = int(ts)
        rows.append(payload)
    return sorted(rows, key=lambda r: r["ts"])


_KEEP_TURN = (
    "turn",
    "route",
    "route_source",
    "latency_ms",
    "events_applied",
    "phase_ms",
    "llm_by_phase",
    "llm_by_tier",
    "llm_calls",
    "llm_requests",
    "llm_failures",
    "llm_attempt_outcomes",
    "llm_providers",
    "fell_back",
    "cost_usd",
    "cost_usd_est",
    "cache_hit_ratio",
    "lock_wait_ms",
    "ack_server_ms",
    "ttfmc_server_ms",
    "ttlt_server_ms",
    "state_server_ms",
    "first_token_server_ms",
    "fallbacks",
    "error",
)
_KEEP_DELIVERY = (
    "ack_server_ms",
    "ttfmc_server_ms",
    "ttlt_server_ms",
    "state_server_ms",
    "first_token_server_ms",
    "early_narrative",
    "early_gain_ms",
    "token_replace",
    "outcome",
    "pseudo_streaming",
)


def join_logs(sessions: list[dict], logs: list[dict]) -> dict:
    turns = [t for s in sessions for t in s.get("turns", [])]
    used = 0
    for t in turns:
        window = [r for r in logs if t["start_ms"] - 500 <= r["ts"] <= t["end_ms"] + 4000]
        for r in window:
            evt = r.get("evt") or r.get("event")
            if evt == "turn" and "server" not in t:
                t["server"] = {k: r.get(k) for k in _KEEP_TURN if k in r}
                used += 1
            elif evt == "turn_delivery" and "delivery" not in t:
                t["delivery"] = {k: r.get(k) for k in _KEEP_DELIVERY if k in r}
                used += 1
        t["other_log_events"] = sorted(
            {str(r.get("evt") or r.get("event")) for r in window} - {"turn", "turn_delivery"}
        )
    return {
        "log_lines": len(logs),
        "joined": used,
        "events_seen": sorted({str(r.get("evt") or r.get("event")) for r in logs}),
    }


def vercel_project(env: dict) -> dict:
    vh = {"Authorization": f"Bearer {env['VERCEL_TOKEN']}"}
    try:
        proj = httpx.get(
            f"https://api.vercel.com/v9/projects/{PROJECT_ID}",
            params={"teamId": TEAM_ID},
            headers=vh,
            timeout=60,
        ).json()
        user = (
            httpx.get("https://api.vercel.com/v2/user", headers=vh, timeout=60)
            .json()
            .get("user", {})
        )
        team = httpx.get(
            f"https://api.vercel.com/v2/teams/{TEAM_ID}", headers=vh, timeout=60
        ).json()
    except httpx.HTTPError as exc:
        return {"error": type(exc).__name__}
    rc = proj.get("resourceConfig") or {}
    drc = proj.get("defaultResourceConfig") or {}
    return {
        "user_plan": (user.get("billing") or {}).get("plan"),
        "team_plan": (team.get("billing") or {}).get("plan"),
        "resourceConfig": {
            k: rc.get(k)
            for k in (
                "fluid",
                "functionDefaultRegions",
                "functionDefaultTimeout",
                "functionDefaultMemoryType",
                "elasticConcurrencyEnabled",
            )
        },
        "defaultResourceConfig": {
            k: drc.get(k)
            for k in (
                "fluid",
                "functionDefaultRegions",
                "functionDefaultTimeout",
                "functionDefaultMemoryType",
            )
        },
        "serverlessFunctionRegion": proj.get("serverlessFunctionRegion"),
        "nodeVersion": proj.get("nodeVersion"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--sessions", type=int, default=4)
    ap.add_argument("--think", type=float, default=6.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--logs-only", action="store_true")
    a = ap.parse_args(argv)
    env = s192.load_env()
    if a.logs_only:
        res = json.loads(open(a.out, encoding="utf-8").read())
        since = f"{int((time.time() * 1000 - res['started_ms']) / 60000) + 5}m"
    else:
        origins = json.loads(
            (s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8")
        )
        res = {"at": s192.now_iso(), "base": a.base, "started_ms": _now_ms(), "think_s": a.think}
        res["vercel"] = vercel_project(env)
        with httpx.Client(timeout=90) as hc:
            first = [_timed(lambda: hc.get(a.base + "/health")) for _ in range(3)]
            res["health_first_3_ms"] = [ms for _, ms in first]
            try:
                hj = first[-1][0].json()
                res["health"] = {
                    k: hj.get(k) for k in ("sha", "git_sha", "version", "status") if k in hj
                }
            except ValueError:
                res["health"] = None
        res["sessions"] = []
        for i in range(a.sessions):
            try:
                res["sessions"].append(session(a.base, env, i, a.think, origins))
            except Exception as exc:  # noqa: BLE001
                res["sessions"].append(
                    {"session": i, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                )
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=1)
            print(
                f"session {i} done: {len(res['sessions'][-1].get('turns', []))} turns", flush=True
            )
        time.sleep(25)
        since = f"{int((time.time() * 1000 - res['started_ms']) / 60000) + 5}m"
    try:
        logs = fetch_logs(env, since, "turn_delivery") + fetch_logs(env, since, "phase_ms")
        res["logs"] = join_logs(res["sessions"], sorted(logs, key=lambda r: r["ts"]))
    except Exception as exc:  # noqa: BLE001
        res["logs"] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    turns = [t for s in res["sessions"] for t in s.get("turns", [])]
    print(
        json.dumps(
            {
                "turns": len(turns),
                "errors": sum(1 for t in turns if t.get("has_error") or t.get("status") != 200),
                "client": {
                    k: _stats([t.get(k) for t in turns])
                    for k in ("ack", "first_chunk", "done", "state")
                },
                "logs": {k: v for k, v in (res.get("logs") or {}).items()},
                "cleanup": [s.get("cleanup") for s in res["sessions"]],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
