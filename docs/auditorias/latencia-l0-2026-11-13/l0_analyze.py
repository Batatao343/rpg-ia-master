"""Resumo da L0 a partir do JSON de l0_measure.py. Offline."""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict


def st(values, digits=0):
    v = sorted(x for x in values if isinstance(x, (int, float)))
    if not v:
        return "n=0"
    p95 = v[min(len(v) - 1, max(0, -(-95 * len(v) // 100) - 1))]
    f = (lambda x: f"{x / 1000:.1f}s") if digits == 0 else (lambda x: f"{x:.0f}ms")
    return f"n={len(v)} p50={f(statistics.median(v))} p95={f(p95)} min={f(v[0])} max={f(v[-1])}"


def main() -> None:
    res = json.load(open(sys.argv[1], encoding="utf-8"))
    print("vercel:", json.dumps(res.get("vercel"), ensure_ascii=False))
    print("health:", res.get("health"), "first3_ms:", res.get("health_first_3_ms"))
    print("logs:", json.dumps(res.get("logs"), ensure_ascii=False))
    sess = res["sessions"]
    print("\n== abertura ==")
    for s in sess:
        print(
            s.get("session"),
            json.dumps(
                {
                    k: v
                    for k, v in (s.get("opening") or {}).items()
                    if k not in ("start_ms", "end_ms")
                }
            ),
            s.get("error"),
            s.get("aborted"),
            s.get("cleanup"),
        )
    turns = [dict(t, session=s["session"]) for s in sess for t in s.get("turns", [])]
    print(
        "\nturnos:",
        len(turns),
        "erros:",
        sum(1 for t in turns if t.get("has_error") or t.get("status") != 200),
        "sem log servidor:",
        sum(1 for t in turns if "server" not in t),
        "sem delivery:",
        sum(1 for t in turns if "delivery" not in t),
    )
    cold = [t for t in turns if (t.get("ack") or 0) > 5000]
    print("ack > 5 s:", len(cold), [round(t["ack"]) for t in cold])
    print("\n== cliente (todos) ==")
    for k in ("ack", "first_chunk", "done", "state"):
        print(f"{k:12}", st([t.get(k) for t in turns]))
    print(
        "state-done  ",
        st([t["state"] - t["done"] for t in turns if t.get("state") and t.get("done")]),
    )
    print(
        "first-ack   ",
        st([t["first_chunk"] - t["ack"] for t in turns if t.get("first_chunk") and t.get("ack")]),
    )
    print(
        "pre getOp   ",
        st([t.get("pre_get_operation_ms") for t in turns], 1),
        sorted({t.get("pre_get_operation_status") for t in turns}),
    )
    print("chars       ", st([t.get("narration_chars") for t in turns], 1))
    print("\n== cliente por categoria (sem fila = a partir do ack) ==")
    by = defaultdict(list)
    for t in turns:
        by[t["category"]].append(t)
    for cat, rows in by.items():
        print(
            f"-- {cat} (n={len(rows)}) rotas servidor: "
            f"{dict((r, sum(1 for t in rows if (t.get('server') or {}).get('route') == r)) for r in {(t.get('server') or {}).get('route') for t in rows})}"
        )
        for k in ("first_chunk", "done", "state"):
            print(f"   {k:11}", st([t[k] - t["ack"] for t in rows if t.get(k) and t.get("ack")]))
        print(
            "   state-done ",
            st([t["state"] - t["done"] for t in rows if t.get("state") and t.get("done")]),
        )
        print("   chars      ", st([t.get("narration_chars") for t in rows], 1))
    print("\n== servidor por rota ==")
    byr = defaultdict(list)
    for t in turns:
        if "server" in t:
            byr[str(t["server"].get("route"))].append(t)
    phases = ("router", "context", "narrator", "archivist", "persistence", "other")
    for route, rows in byr.items():
        print(f"-- rota {route} (n={len(rows)})")
        print("   latency_ms  ", st([t["server"].get("latency_ms") for t in rows]))
        for p in phases:
            print(
                f"   fase {p:11}", st([(t["server"].get("phase_ms") or {}).get(p) for t in rows], 1)
            )
        print("   llm_calls   ", st([t["server"].get("llm_calls") for t in rows], 1))
    print("\n== servidor (todos) ==")
    srv = [t for t in turns if "server" in t]
    for p in phases:
        print(
            f"fase {p:11}",
            st([(t["server"].get("phase_ms") or {}).get(p) for t in srv], 1),
            " soma=",
            sum((t["server"].get("phase_ms") or {}).get(p) or 0 for t in srv),
        )
    print("llm_by_phase exemplo:", [t["server"].get("llm_by_phase") for t in srv[:3]])
    tiers: dict = defaultdict(
        lambda: {"attempts": 0, "failed": 0, "fallbacks": 0, "latency_ms": 0, "cost": 0.0}
    )
    for t in srv:
        for tier, row in (t["server"].get("llm_by_tier") or {}).items():
            for k in ("attempts", "failed", "fallbacks", "latency_ms"):
                tiers[tier][k] += row.get(k) or 0
            tiers[tier]["cost"] += float(row.get("cost_usd") or 0)
    for tier, row in tiers.items():
        avg = row["latency_ms"] / row["attempts"] if row["attempts"] else 0
        print(
            f"tier {tier}: {row}  media/chamada={avg:.0f}ms  por turno={row['attempts'] / max(1, len(srv)):.2f}"
        )
    print(
        "llm_calls/turno",
        st([t["server"].get("llm_calls") for t in srv], 1),
        "soma=",
        sum(t["server"].get("llm_calls") or 0 for t in srv),
    )
    print(
        "outcomes:",
        dict(
            sum(
                (
                    __import__("collections").Counter(t["server"].get("llm_attempt_outcomes") or {})
                    for t in srv
                ),
                __import__("collections").Counter(),
            )
        ),
    )
    print(
        "providers:",
        dict(
            sum(
                (
                    __import__("collections").Counter(t["server"].get("llm_providers") or {})
                    for t in srv
                ),
                __import__("collections").Counter(),
            )
        ),
    )
    print(
        "custo total US$:",
        round(
            sum(
                float(t["server"].get("cost_usd") or t["server"].get("cost_usd_est") or 0)
                for t in srv
            ),
            4,
        ),
    )
    print(
        "cache_hit_ratio",
        st([(t["server"].get("cache_hit_ratio") or 0) * 1000 for t in srv], 1),
        "(x1000)",
    )
    print(
        "route_source:",
        dict(__import__("collections").Counter(str(t["server"].get("route_source")) for t in srv)),
    )
    dl = [t for t in turns if "delivery" in t]
    print("\n== delivery ==")
    for k in (
        "ack_server_ms",
        "first_token_server_ms",
        "ttfmc_server_ms",
        "ttlt_server_ms",
        "state_server_ms",
        "early_gain_ms",
    ):
        print(f"{k:22}", st([t["delivery"].get(k) for t in dl]))
    print(
        "early_narrative:",
        sum(1 for t in dl if t["delivery"].get("early_narrative")),
        "/",
        len(dl),
        "replace:",
        sum(1 for t in dl if t["delivery"].get("token_replace")),
        "pseudo:",
        sum(1 for t in dl if t["delivery"].get("pseudo_streaming")),
    )
    print(
        "ttfmc-first_token",
        st(
            [
                t["delivery"]["ttfmc_server_ms"] - t["delivery"]["first_token_server_ms"]
                for t in dl
                if t["delivery"].get("ttfmc_server_ms") is not None
                and t["delivery"].get("first_token_server_ms") is not None
            ]
        ),
    )
    print(
        "cliente_state - servidor_state",
        st(
            [
                t["state"] - t["delivery"]["state_server_ms"]
                for t in dl
                if t.get("state") and t["delivery"].get("state_server_ms")
            ]
        ),
    )
    print("\n== persistencia x indice do turno ==")
    byi = defaultdict(list)
    for t in srv:
        byi[t["i"]].append((t["server"].get("phase_ms") or {}).get("persistence"))
    print({i: [x for x in v] for i, v in sorted(byi.items())})
    print("\n== banco / idas leves ==")
    for s in sess:
        db = s.get("db") or {}
        print(
            s.get("session"),
            {
                k: db.get(k)
                for k in (
                    "version",
                    "state_stored_bytes",
                    "state_text_bytes",
                    "event_log_len",
                    "game_events_rows",
                )
            },
        )
        print("   warm:", json.dumps(s.get("warm")))
    print("\n== turno a turno ==")
    for t in turns:
        sv, d = t.get("server") or {}, t.get("delivery") or {}
        print(
            t["session"],
            t["i"],
            f"{t['category']:9}",
            f"rota={str(sv.get('route')):14}",
            f"ack={t.get('ack')}",
            f"first={t.get('first_chunk')}",
            f"done={t.get('done')}",
            f"state={t.get('state')}",
            f"chars={t.get('narration_chars')}",
            f"fases={sv.get('phase_ms')}",
            f"calls={sv.get('llm_calls')}",
            f"gain={d.get('early_gain_ms')}",
            f"err={t.get('has_error')}",
            t.get("other_log_events"),
        )


if __name__ == "__main__":
    main()
