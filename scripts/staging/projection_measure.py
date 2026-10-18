"""SPEC-213 no staging: latencia visivel ao jogador + corretude das projecoes derivadas do arquivista.

Roda N turnos SSE reais (usuario sintetico, DeepSeek) com tempo de leitura entre turnos, mede no
cliente o que o jogador espera (fim da narracao/estado) e, no fim, confere no banco que os derivados
(resumo/memoria/cronica) chegaram: jobs `project_archive`, versao canonica monotonica, sem duplicata,
cronica visivel no reload. Saida: so contagens/tempos/status (sem ids, sem texto, sem segredos).

Uso: python -m scripts.staging.projection_measure --label inline --turns 15 --think 8
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from uuid import uuid4

import httpx

from scripts.staging import s192
from scripts.staging.e2e_session import _h

ACTIONS = [
    "Observo ao redor com cuidado e procuro alguém para conversar.",
    "Pergunto à pessoa mais próxima o que tem acontecido por aqui.",
    "Peço detalhes sobre os perigos da região.",
    "Examino o chão e os cantos em busca de algo útil.",
    "Recolho o que encontrei e guardo na bolsa.",
    "Agradeço e pergunto se há trabalho para um viajante.",
    "Aceito a tarefa e pergunto por onde começar.",
    "Sigo pela rua principal observando as pessoas.",
    "Procuro um mercador e pergunto o que ele vende.",
    "Pergunto ao mercador sobre rumores recentes.",
    "Examino um objeto estranho na banca.",
    "Converso com um guarda sobre a segurança local.",
    "Descanso um instante num canto tranquilo.",
    "Revejo mentalmente o que aprendi até agora.",
    "Procuro pistas sobre a tarefa que aceitei.",
    "Pergunto a um morador se viu algo fora do comum.",
    "Sigo a pista mais promissora com cautela.",
    "Examino as marcas que encontrei.",
]


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def stream_turn(c: httpx.Client, base: str, csrf: str, game_id: str, text: str) -> dict:
    """Um turno SSE, com marcas do cliente: ack, 1o chunk, done (= fim do que o jogador le), state, close."""
    t0 = time.perf_counter()
    marks: dict = {}
    lines: list[str] = []
    with c.stream("POST", f"{base}/game/action/stream", headers=_h(base, csrf),
                  json={"input_text": text, "game_id": game_id, "action_id": str(uuid4())}, timeout=240) as r:
        status = r.status_code
        ev = None
        for ln in r.iter_lines():
            lines.append(ln)
            if ln.startswith("event:"):
                ev = ln.split(":", 1)[1].strip()
                if ev == "accepted" and "ack" not in marks:
                    marks["ack"] = _ms(t0)
                if ev == "state" and "state" not in marks:
                    marks["state"] = _ms(t0)
            elif ln.startswith("data:") and ev == "narrative":
                if '"done": true' in ln or '"done":true' in ln:
                    marks.setdefault("done", _ms(t0))
                else:
                    marks.setdefault("first_chunk", _ms(t0))
    marks["close"] = _ms(t0)
    events = s192.parse_sse(lines + [""])
    state = next((e["data"] for e in reversed(events) if e["event"] == "state"), None) or {}
    narr = "".join(e["data"].get("chunk", "") for e in events
                   if e["event"] == "narrative" and isinstance(e["data"], dict))
    proj = state.get("projections") or {}
    return {"status": status, **marks, "narration_chars": len(narr),
            "has_error": any(e["event"] == "error" for e in events),
            "turn_count": (state.get("world") or {}).get("turn_count"),
            "canonical_version": proj.get("canonical_version"),
            "projection_status": {k: (proj.get(k) or {}).get("status") for k in ("summary", "memory", "chronicle")}}


def _stats(values: list) -> dict:
    v = [x for x in values if isinstance(x, (int, float))]
    return {"n": len(v), "p50": round(statistics.median(v), 1) if v else None,
            "p95": s192.pct(v, 95), "max": round(max(v), 1) if v else None}


def _db_snapshot(env: dict, game_id: str) -> dict:
    from services.audit_trace import expand_trace

    def fn(conn):
        jobs = conn.execute(
            "select status, attempts, lease_owner, last_error_code, dedupe_key, "
            "extract(epoch from (updated_at - created_at))*1000 as ms from app.jobs "
            "where game_id::text=%s and kind='project_archive' order by created_at", (game_id,)).fetchall()
        doc = conn.execute("select version, state from app.games where id::text=%s", (game_id,)).fetchone()
        mem = conn.execute(
            "select count(*) as n, count(distinct content_sha256) as distinct_n from app.memory_documents "
            "where game_id::text=%s", (game_id,)).fetchone()
        return jobs, doc, mem
    jobs, doc, mem = s192.query(env, fn)
    st = (doc or {}).get("state") or {}
    ps = st.get("projection_state") or {}
    trace = expand_trace(st.get("audit_trace") or [])
    timing = [{"turn": t.get("turn"), "phase_ms": (t.get("timing") or {}).get("phase_ms"),
               "lock_wait_ms": (t.get("timing") or {}).get("lock_wait_ms"),
               "providers": (t.get("timing") or {}).get("providers_used"),
               "llm_failed_attempts": (t.get("timing") or {}).get("llm_failed_attempts")} for t in trace]
    keys = [j["dedupe_key"] for j in jobs]
    return {
        "jobs": {"n": len(jobs), "distinct_keys": len(set(keys)),
                 "by_status": {s: sum(1 for j in jobs if j["status"] == s) for s in {j["status"] for j in jobs}},
                 "lease_owners": sorted({str(j["lease_owner"]) for j in jobs}),
                 "attempts_max": max((j["attempts"] for j in jobs), default=0),
                 "errors": sorted({str(j["last_error_code"]) for j in jobs if j["last_error_code"]}),
                 "created_to_final_ms": _stats([float(j["ms"]) for j in jobs if j["status"] == "succeeded"])},
        "projection_state": {"canonical_version": ps.get("canonical_version"),
                             **{k: {"status": (ps.get(k) or {}).get("status"),
                                    "projected_version": (ps.get(k) or {}).get("projected_version")}
                                for k in ("summary", "memory", "chronicle")}},
        "pending_derived": bool(st.get("pending_derived")),
        "memory_rows": {"n": mem["n"], "distinct_content": mem["distinct_n"]},
        "summary_chars": len(st.get("narrative_summary") or ""),
        "chronicle_entries_by_kind": _count([e.get("kind") for ch in st.get("chronicle") or []
                                             for e in ch.get("entries") or []]),
        "evidence_rejections_by_channel": _count([r.get("channel") for r in st.get("evidence_rejections") or []
                                                  if isinstance(r, dict)]),
        "archivist_runs": sum(1 for t in timing if ((t.get("phase_ms") or {}).get("archivist") or 0) > 500),
        "timing": timing,
    }


def _count(values: list) -> dict:
    out: dict = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def _settled(snap: dict) -> bool:
    ps = snap["projection_state"]
    cv = ps["canonical_version"]
    jobs_open = sum(n for s, n in snap["jobs"]["by_status"].items() if s in ("queued", "running", "retry"))
    return (not snap["pending_derived"] and jobs_open == 0
            and all(ps[k]["status"] == "completed" and ps[k]["projected_version"] == cv
                    for k in ("summary", "memory", "chronicle")))


def run(base: str, env: dict, label: str, turns: int, think: float, settle_s: float) -> dict:
    admin = s192.Admin(env)
    user = admin.create_user()
    out: dict = {"label": label, "at": s192.now_iso(), "turns_requested": turns, "think_s": think}
    game_id = ""
    c = httpx.Client(timeout=60, follow_redirects=False, transport=httpx.HTTPTransport(retries=3))
    try:
        r = s192.app_login(c, base, user)
        csrf = (r.json() if r.status_code == 200 else {}).get("csrf_token") or c.cookies.get("rpg_csrf") or ""
        origins = json.loads((s192.common.ROOT / "data" / "origins.json").read_text(encoding="utf-8"))
        body = {"name": "Spec213 Heroi", "race": origins["races"][0]["name"], "class_name": "Devoto do Abismo",
                "region": origins["regions"][0]["name"], "level": 1, "action_id": str(uuid4())}
        r = c.post(f"{base}/game/new", headers=_h(base, csrf), json=body, timeout=180)
        gj = r.json() if r.status_code == 200 else {}
        game_id = gj.get("game_id", "")
        out["new_game"] = {"status": r.status_code, "simulated": gj.get("simulated")}
        if not game_id:
            raise RuntimeError(f"new game failed: {r.status_code}")
        rows = []
        for i in range(turns):
            rows.append(stream_turn(c, base, csrf, game_id, ACTIONS[i % len(ACTIONS)]))
            if i < turns - 1:
                time.sleep(think)
        out["turns"] = rows
        out["client"] = {k: _stats([t.get(k) for t in rows]) for k in ("ack", "first_chunk", "done", "state", "close")}
        cvs = [t["canonical_version"] for t in rows]
        tcs = [t["turn_count"] for t in rows]
        out["checks"] = {
            "all_ok": all(t["status"] == 200 and not t["has_error"] and t.get("done") and t["narration_chars"] > 0
                          for t in rows),
            "turn_counts_consecutive": all(b == a + 1 for a, b in zip(tcs, tcs[1:])),
            "canonical_version_strictly_monotonic": all(isinstance(a, int) and isinstance(b, int) and b > a
                                                        for a, b in zip(cvs, cvs[1:])),
            "status_seen_in_responses": sorted({s for t in rows for s in t["projection_status"].values() if s}),
        }
        t0 = time.monotonic()
        snap = _db_snapshot(env, game_id)
        while not _settled(snap) and time.monotonic() - t0 < settle_s:
            time.sleep(5)
            snap = _db_snapshot(env, game_id)
        out["settle_s"] = round(time.monotonic() - t0, 1)
        out["db"] = snap
        out["checks"]["derived_landed"] = _settled(snap)
        out["checks"]["no_duplicate_jobs"] = snap["jobs"]["n"] == snap["jobs"]["distinct_keys"]
        out["checks"]["no_duplicate_memory"] = snap["memory_rows"]["n"] == snap["memory_rows"]["distinct_content"]
        r = c.get(f"{base}/game/state", params={"game_id": game_id})
        st = r.json() if r.status_code == 200 else {}
        chron = st.get("chronicle") or []
        out["reload"] = {"status": r.status_code, "projections": st.get("projections"),
                         "chronicle_chapters": len(chron),
                         "chronicle_entries": sum(len(ch.get("entries") or []) for ch in chron),
                         "summary_chars": len(st.get("narrative_summary") or "")}
        # Entradas de prosa sao raras (o LLM quase nunca devolve chronicle_entry) e marcos dependem de eventos:
        # o que se confere e a cronica servida no reload com a projecao concluida na versao canonica.
        rp = (st.get("projections") or {}).get("chronicle") or {}
        out["checks"]["reload_chronicle_visible"] = (
            r.status_code == 200 and out["reload"]["chronicle_chapters"] > 0 and rp.get("status") == "completed"
            and rp.get("projected_version") == (st.get("projections") or {}).get("canonical_version"))
    finally:
        cleanup: dict = {}
        if game_id:
            try:
                cleanup["games_deleted"] = s192.query(env, lambda conn: conn.execute(
                    "delete from app.games where id::text=%s", (game_id,)).rowcount)
            except Exception as exc:  # noqa: BLE001
                cleanup["games_error"] = type(exc).__name__
        cleanup["user_delete_status"] = admin.delete_user(user["id"])
        out["cleanup"] = cleanup
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--label", required=True)
    ap.add_argument("--turns", type=int, default=15)
    ap.add_argument("--think", type=float, default=8.0, help="segundos de leitura entre turnos")
    ap.add_argument("--settle", type=float, default=180.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = run(a.base, s192.load_env(), a.label, a.turns, a.think, a.settle)
    s192.common.write_evidence(a.label, res, a.out)
    print(json.dumps({"label": a.label, "client": res.get("client"), "checks": res.get("checks"),
                      "cleanup": res.get("cleanup")}, ensure_ascii=False))
    return 0 if all(v for k, v in (res.get("checks") or {}).items() if isinstance(v, bool)) else 1


if __name__ == "__main__":
    sys.exit(main())
