"""SPEC-217: Jev em ``primary`` no staging (aprovacao do dono, 2026-10-18).

Roda ~20 turnos SSE reais (usuarios sinteticos, narrador DeepSeek) com acoes variadas (conversa com NPC,
combate, loja/fabricacao/tesouro, inspecao de objetos, viagem) e junta, por ``x-vercel-id``, as linhas
``jev.primary`` dos logs da funcao. Le tambem o ``phase_ms.router`` de cada turno no ``audit_trace`` do jogo
antes de apaga-lo. Mede: fracao decidida pelo Jev, fallbacks (motivos), latencia do router (Jev × CLASSIFY ×
gate Python), TTLT do turno e erros. Teto: 40 chamadas ao Jev (1 por turno no maximo).

Uso: python -m scripts.staging.jev_primary_measure --out docs/spec217/evidence/primary-staging-2026-10-18.json
     [--narration-out <scratch>.json]   # trechos da narracao p/ revisao manual (fora do repo)
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from scripts.staging import jev_shadow_measure as shadow
from scripts.staging import projection_measure, s192

SESSIONS: list[list[tuple[str, str]]] = [
    [
        ("story", "Examino os muros da cidade com atenção."),
        ("talk", "Pergunto ao guarda se há trabalho para um viajante."),
        ("loot_shop", "Procuro um mercador e compro uma tocha."),
        ("story", "Inspeciono a carroça abandonada perto do portão."),
        ("loot_craft", "Fabrico bandagens com o tecido limpo que carrego."),
        ("loot_take", "Vasculho o baú esquecido no canto da estalagem."),
        ("talk", "Pergunto ao taverneiro que rumores correm pela estrada."),
        ("loot_shop", "Vendo a adaga velha ao mercador."),
        ("travel", "Viajo para a próxima cidade."),
        ("combat", "Saco a espada e ataco o bandido mais próximo."),
    ],
    [
        ("story", "Examino um objeto estranho na banca do mercado."),
        ("talk", "Cumprimento o ferreiro e pergunto quanto custa consertar meu escudo."),
        ("loot_shop", "Compro uma poção de cura."),
        ("loot_take", "Pego a moeda caída no chão."),
        ("story", "Investigo as pegadas perto da porta."),
        ("loot_craft", "Forjo uma ponta de flecha na bigorna."),
        ("talk", "Converso com a mulher na praça sobre o que houve com a vila."),
        ("loot_take", "Abro a caixa trancada que encontrei."),
        ("story", "Sigo a trilha até a floresta."),
        ("combat", "Ataco o lobo que avança contra mim."),
    ],
]

_NARRATION: list[dict] = []


def _stream_turn_keep_text(c, base, csrf, game_id, text):
    """``projection_measure.stream_turn`` + trecho da narracao (so p/ o arquivo de revisao fora do repo)."""
    captured: list[str] = []
    orig_parse = s192.parse_sse

    def parse(lines):
        events = orig_parse(lines)
        captured.append(
            "".join(
                e["data"].get("chunk", "")
                for e in events
                if e["event"] == "narrative" and isinstance(e["data"], dict)
            )
        )
        return events

    s192.parse_sse = parse
    try:
        row = projection_measure.stream_turn(c, base, csrf, game_id, text)
    finally:
        s192.parse_sse = orig_parse
    _NARRATION.append({"action": text, "narration_head": (captured[-1] if captured else "")[:400]})
    return row


def _router_timing(env: dict):
    from services.audit_trace import expand_trace

    def before_delete(game_id: str) -> dict:
        doc = s192.query(
            env,
            lambda conn: conn.execute(
                "select state from app.games where id::text=%s", (game_id,)
            ).fetchone(),
        )
        trace = expand_trace(((doc or {}).get("state") or {}).get("audit_trace") or [])
        return {
            str(t.get("turn")): {
                "router_ms": ((t.get("timing") or {}).get("phase_ms") or {}).get("router"),
                "providers": (t.get("timing") or {}).get("providers_used"),
            }
            for t in trace
        }

    return before_delete


def summarize(turns: list[dict], logs: list[dict]) -> dict:
    obs = [t["jev"] for t in turns if t.get("jev")]
    decided = [o for o in obs if o.get("outcome") == "primary"]
    reasons: dict = {}
    outcomes: dict = {}
    for o in obs:
        outcomes[o.get("outcome")] = outcomes.get(o.get("outcome"), 0) + 1
        if o.get("outcome") != "primary":
            key = o.get("reason") or o.get("outcome")
            reasons[key] = reasons.get(key, 0) + 1

    def router(group):
        return s192.stats(
            [t["router_ms"] for t in group if isinstance(t.get("router_ms"), (int, float))]
        )

    jev_turns = [t for t in turns if (t.get("jev") or {}).get("outcome") == "primary"]
    fb_turns = [t for t in turns if t.get("jev") and t["jev"].get("outcome") != "primary"]
    gate_turns = [t for t in turns if not t.get("jev")]
    route_vs_label = {}
    for t in jev_turns:
        key = f"{t['category']}->{t['jev'].get('jev_route')}"
        route_vs_label[key] = route_vs_label.get(key, 0) + 1
    lat = [float(o["latency_ms"]) for o in obs if isinstance(o.get("latency_ms"), (int, float))]
    waits = [float(o.get("wait_ms") or 0) for o in obs]
    return {
        "turns": len(turns),
        "turns_ok": sum(t["status"] == 200 and not t["has_error"] for t in turns),
        "jev_calls": len(logs),
        "jev_observations_joined": len(obs),
        "jev_decided": len(decided),
        "jev_decided_share_of_turns": round(len(decided) / len(turns), 4) if turns else None,
        "jev_decided_share_of_calls": round(len(decided) / len(obs), 4) if obs else None,
        "outcomes": outcomes,
        "fallback_reasons": reasons,
        "python_gate_turns": len(gate_turns),
        "label_to_jev_route": dict(sorted(route_vs_label.items())),
        "jev_latency_ms": s192.stats(lat),
        "router_wait_for_jev_ms": s192.stats(waits),
        "router_phase_ms": {
            "jev_decided": router(jev_turns),
            "classify_fallback": router(fb_turns),
            "python_gate": router(gate_turns),
            "all": router(turns),
        },
        "turn_ttlt_ms": s192.stats(
            [t["done_ms"] for t in turns if isinstance(t.get("done_ms"), (int, float))]
        ),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=s192.BASE)
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--think", type=float, default=1.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--narration-out")
    a = ap.parse_args(argv)
    if a.max_turns > 40:
        print("recusado: teto de 40 chamadas ao Jev", file=sys.stderr)
        return 2
    env = s192.load_env()
    shadow.stream_turn = _stream_turn_keep_text  # o driver do shadow usa este nome
    started = time.time()
    turns, cleanup = shadow.play(a.base, env, a.max_turns, a.think, SESSIONS, _router_timing(env))
    time.sleep(20)  # deixa os logs da funcao chegarem
    logs = shadow.fetch_shadow_logs(
        env, f"{int((time.time() - started) / 60) + 5}m", event="jev.primary"
    )
    for turn in shadow.join(turns, logs):
        turn["jev"] = turn.pop("shadow", None)
        per_game = (cleanup.get("per_game") or {}).get(turn["session"]) or {}
        timing = per_game.get(str(turn.get("turn_count"))) or {}
        turn["router_ms"] = timing.get("router_ms")
        turn["providers"] = timing.get("providers")
    if a.narration_out:
        with open(a.narration_out, "w", encoding="utf-8") as fh:
            json.dump(_NARRATION, fh, ensure_ascii=False, indent=1)
    cleanup.pop("per_game", None)
    res = {
        "at": s192.now_iso(),
        "turns": turns,
        "cleanup": cleanup,
        "summary": summarize(turns, logs),
    }
    s192.common.write_evidence("spec217_primary", res, a.out)
    print(json.dumps({"summary": res["summary"], "cleanup": cleanup}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
