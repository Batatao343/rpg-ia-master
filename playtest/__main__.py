"""CLI do harness de playtest.

    uv run python -m playtest run --profile explorador --turns 50 --seed 42
    uv run python -m playtest run --all --turns 30
    uv run python -m playtest run --profile diplomatico --turns 4 --real
    uv run python -m playtest report <run_id> [--baseline <run_id>]

`run` grava telemetria (JSONL + summary) por campanha num diretório de run e
imprime o run_id (spec 5.3). `report` agrega um run em Markdown.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from playtest.profiles import PROFILES
from playtest.runner import run_campaign, CampaignResult


def _route_mais_usada(res: CampaignResult) -> str:
    c = Counter(r.route for r in res.history if r.route)
    return c.most_common(1)[0][0] if c else "—"


def _print_resumo(res: CampaignResult) -> None:
    n_err = len(res.errors)
    n_viol = len([v for v in res.violations if v.get("severity") == "error"])
    n_warn = len([v for v in res.violations if v.get("severity") == "warning"])
    linha = (f"  {res.profile:<14} turnos={res.turns_completed:<3} "
             f"erros={n_err:<2} violações(err/warn)={n_viol}/{n_warn} "
             f"rota_top={_route_mais_usada(res)}")
    if res.aborted_reason:
        linha += f"  [ABORTADO: {res.aborted_reason}]"
    print(linha)
    for e in res.errors[:3]:
        print(f"      ! turno {e['turn']}: {e['exc'][:100]}")


def _cmd_run(args) -> int:
    from playtest import telemetry
    run_id = telemetry.new_run_id()
    profiles = sorted(PROFILES) if args.all else [args.profile]
    if not profiles or profiles == [None]:
        print("erro: informe --profile <nome> ou --all", file=sys.stderr)
        return 2

    print(f"== playtest run {run_id} ==  perfis={profiles} turnos={args.turns} "
          f"seed={args.seed} real={args.real}"
          + (f" classe={args.class_name}" if args.class_name else ""))
    exit_code = 0
    for profile in profiles:
        res = run_campaign(
            profile, turns=args.turns, seed=args.seed,
            use_real_llm=args.real, invariants=not args.no_invariants,
            max_requests=args.max_requests, max_cost=args.max_cost,
            class_name=args.class_name,
        )
        stem = None
        if args.class_name:
            import re as _re
            cls = ((res.final_state or {}).get("player") or {}).get("class_name") or args.class_name
            slug = _re.sub(r"\W+", "_", cls.lower()).strip("_")
            stem = f"{profile}_{slug}_{res.seed}"
        telemetry.persist_campaign(run_id, res, stem=stem)
        _print_resumo(res)
        if any(v.get("severity") == "error" for v in res.violations):
            exit_code = 1
    run_dir = telemetry.run_dir(run_id)
    print(f"\nTelemetria: {run_dir}\n  relatório: uv run python -m playtest report {run_id}")
    return exit_code


def _cmd_report(args) -> int:
    from playtest import report, telemetry
    run_dir = telemetry.run_dir(args.run_id)
    baseline_dir = telemetry.run_dir(args.baseline) if args.baseline else None
    rep = report.aggregate(run_dir, baseline_dir)
    md = report.render_markdown(rep)
    out = telemetry.report_path(args.run_id)
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Relatório escrito em {out}")
    return 0


def _cmd_transcript(args) -> int:
    import os
    from playtest import report, telemetry
    run_dir = telemetry.run_dir(args.run_id)
    md = report.render_transcript(run_dir)
    out = os.path.join(run_dir, "transcript.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Transcrito escrito em {out}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="playtest", description="Harness de playtest agêntico")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="roda campanha(s) de playtest")
    pr.add_argument("--profile", choices=sorted(PROFILES), default=None)
    pr.add_argument("--all", action="store_true", help="roda os 10 perfis em série")
    pr.add_argument("--turns", type=int, default=50)
    pr.add_argument("--seed", type=int, default=0)
    pr.add_argument("--class", dest="class_name", default=None,
                    help="classe do personagem (nome ou slug, ex.: sangromante); default Devoto do Abismo")
    pr.add_argument("--real", action="store_true", help="usa LLM real (opt-in, consciente de quota/custo)")
    pr.add_argument("--no-invariants", action="store_true", help="desliga os checks de invariante 5.2")
    pr.add_argument("--max-requests", type=int, default=15, help="teto de invokes de LLM (--real); 0 desliga")
    pr.add_argument("--max-cost", type=float, default=0.0, help="teto de custo USD estimado (--real); 0 desliga")
    pr.set_defaults(func=_cmd_run)

    prp = sub.add_parser("report", help="agrega um run em Markdown")
    prp.add_argument("run_id")
    prp.add_argument("--baseline", default=None, help="run_id anterior p/ deltas")
    prp.set_defaults(func=_cmd_report)

    prt = sub.add_parser("transcript", help="transcrito ação→narração por turno (julgar o prompt)")
    prt.add_argument("run_id")
    prt.set_defaults(func=_cmd_transcript)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
