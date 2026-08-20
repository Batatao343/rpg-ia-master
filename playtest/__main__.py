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

# O harness também é executado diretamente no console Windows. Sem este ajuste,
# símbolos usados no help/relatório (por exemplo, ação→narração) quebram em cp1252.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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
    from playtest import scenarios
    run_id = telemetry.new_run_id()
    selectors = int(bool(args.profile)) + int(bool(args.all)) + int(bool(args.scenario))
    if selectors != 1:
        print(
            "erro: informe exatamente um de --profile, --all ou --scenario",
            file=sys.stderr,
        )
        return 2
    profiles = (
        [scenarios.profile_for(args.scenario)]
        if args.scenario else (sorted(PROFILES) if args.all else [args.profile])
    )
    print(f"== playtest run {run_id} ==  perfis={profiles} turnos={args.turns} "
          f"seed={args.seed} real={args.real}"
          + (f" cenário={args.scenario}" if args.scenario else "")
          + (f" classe={args.class_name}" if args.class_name else "")
          + f" nivel_inicial={args.start_level}")
    exit_code = 0
    final_status = "complete"
    final_reason = None
    telemetry.begin_run(
        run_id,
        profiles=profiles,
        turns=args.turns,
        seed=args.seed,
        real=args.real,
        class_name=args.class_name,
        invariants_enabled=not args.no_invariants,
        scenario=args.scenario,
        start_level=args.start_level,
    )
    try:
        for profile in profiles:
            try:
                res = run_campaign(
                    profile, turns=args.turns, seed=args.seed,
                    use_real_llm=args.real, invariants=not args.no_invariants,
                    max_requests=args.max_requests, max_cost=args.max_cost,
                    class_name=args.class_name,
                    turn_timeout_seconds=args.turn_timeout,
                    scenario=args.scenario,
                    start_level=args.start_level,
                    on_turn_end=lambda _state, _turn: telemetry.touch_run(run_id),
                )
            except Exception as exc:
                print(
                    f"  {profile:<14} FALHA antes de persistir: {exc!r}",
                    file=sys.stderr,
                )
                exit_code = 1
                continue
            stem = None
            if args.class_name:
                import re as _re
                cls = ((res.final_state or {}).get("player") or {}).get("class_name") or args.class_name
                slug = _re.sub(r"\W+", "_", cls.lower()).strip("_")
                stem = f"{profile}_{slug}_{res.seed}"
            summary = telemetry.persist_campaign(run_id, res, stem=stem)
            _print_resumo(res)
            if (
                res.errors
                or res.aborted_reason
                or res.turns_completed != args.turns
                or int(summary.get("observability_errors", 0) or 0) > 0
                or any(
                    violation.get("severity") == "error"
                    for violation in res.violations
                )
            ):
                exit_code = 1
            if res.aborted_reason and res.aborted_reason.startswith("timeout:"):
                final_status = "aborted"
                final_reason = res.aborted_reason
                break
    except KeyboardInterrupt:
        exit_code = 130
        final_status = "aborted"
        final_reason = "keyboard_interrupt"
        print("\nplaytest interrompido; manifesto marcado como aborted.", file=sys.stderr)
    finally:
        completeness = telemetry.finish_run(
            run_id,
            status=(
                final_status if final_status == "aborted"
                else ("failed" if exit_code else "complete")
            ),
            reason=final_reason,
        )
        if not completeness.get("complete"):
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
    return 0 if rep.complete else 1


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


def _cmd_merchant_suite(args) -> int:
    """Cinco campanhas/classes offline; uma Sangromante no modo real."""
    from playtest import telemetry

    if args.real and args.max_cost <= 0:
        print("erro: merchant-suite --real exige --max-cost positivo aprovado", file=sys.stderr)
        return 2
    classes = [
        "Devoto do Abismo", "Sangromante", "Corruptor",
        "Arcanista Cinzento", "Médico de Campo",
    ]
    if args.real:
        classes = ["Sangromante"]
    labels = [f"comerciante:{index + 1}" for index in range(len(classes))]
    run_id = telemetry.new_run_id()
    telemetry.begin_run(
        run_id, profiles=labels, turns=args.turns, seed=args.seed,
        real=args.real, class_name=None, invariants_enabled=True,
        seeds_by_profile={label: args.seed + index for index, label in enumerate(labels)},
    )
    exit_code = 0
    try:
        for index, class_name in enumerate(classes):
            seed = args.seed + index
            result = run_campaign(
                "comerciante", turns=args.turns, seed=seed,
                class_name=class_name, use_real_llm=args.real,
                max_requests=args.max_requests, max_cost=args.max_cost,
                turn_timeout_seconds=args.turn_timeout,
                on_turn_end=lambda _state, _turn: telemetry.touch_run(run_id),
            )
            result.profile = labels[index]
            summary = telemetry.persist_campaign(
                run_id, result, stem=f"merchant_{index + 1}_{seed}",
            )
            _print_resumo(result)
            if (
                result.errors or result.aborted_reason
                or result.turns_completed != args.turns
                or int(summary.get("error_violations", 0) or 0)
            ):
                exit_code = 1
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        telemetry.finish_run(
            run_id, status="complete" if exit_code == 0 else "failed",
            reason=None if exit_code == 0 else "campaign_failure",
        )
    print(f"\nMerchant suite: {telemetry.run_dir(run_id)}")
    return exit_code


def _run_matrix_suite(args) -> int:
    """Roda a matriz fixa A/B sequencialmente e preserva o pareamento."""
    from playtest import telemetry
    from playtest.matrix import LONGRUN_MATRIX, case_label

    if args.real and (args.max_cost <= 0 or args.max_requests <= 0):
        print(
            "erro: matrix-suite --real exige --max-cost e --max-requests positivos por campanha",
            file=sys.stderr,
        )
        return 2
    labels = [case_label(case) for case in LONGRUN_MATRIX]
    rows = [{**case, "label": case_label(case)} for case in LONGRUN_MATRIX]
    run_id = telemetry.new_run_id()
    telemetry.begin_run(
        run_id, profiles=labels, turns=args.turns, seed=LONGRUN_MATRIX[0]["seed"],
        real=args.real, class_name=None, invariants_enabled=True,
        seeds_by_profile={case_label(case): case["seed"] for case in LONGRUN_MATRIX},
        campaign_matrix=rows,
        routes_profile=args.routes_profile,
        provider_min_interval_seconds=args.groq_min_interval,
    )
    print(
        f"== matriz {args.label} {run_id} == campanhas=10 turnos={args.turns} "
        f"real={args.real} teto_por_campanha=${args.max_cost:.2f}/"
        f"{args.max_requests} requests · teto_agregado=${args.max_cost * 10:.2f}/"
        f"{args.max_requests * 10} requests"
    )
    exit_code = 0
    interrupted = False
    try:
        for case in LONGRUN_MATRIX:
            label = case_label(case)
            print(
                f"\n[{case['index']:02d}/10] {case['profile']} · "
                f"{case['class_name']} · nível {case['start_level']} · seed {case['seed']}"
            )
            result = run_campaign(
                case["profile"], turns=args.turns, seed=case["seed"],
                class_name=case["class_name"], start_level=case["start_level"],
                use_real_llm=args.real, max_requests=args.max_requests,
                max_cost=args.max_cost, turn_timeout_seconds=args.turn_timeout,
                on_turn_end=lambda _state, _turn: telemetry.touch_run(run_id),
                provider_min_interval_seconds=args.groq_min_interval,
            )
            result.profile = label
            summary = telemetry.persist_campaign(
                run_id, result, stem=f"matrix_{case['index']:02d}_{case['seed']}",
            )
            _print_resumo(result)
            if (
                result.errors or result.aborted_reason
                or result.turns_completed != args.turns
                or int(summary.get("error_violations", 0) or 0)
                or int(summary.get("observability_errors", 0) or 0)
            ):
                exit_code = 1
    except KeyboardInterrupt:
        interrupted = True
        exit_code = 130
    finally:
        telemetry.finish_run(
            run_id,
            status="aborted" if interrupted else ("complete" if not exit_code else "failed"),
            reason="keyboard_interrupt" if interrupted else (None if not exit_code else "campaign_failure"),
        )
    print(f"\nMatriz {args.label}: {telemetry.run_dir(run_id)}")
    return exit_code


def _cmd_matrix_suite(args) -> int:
    from playtest.provider_profiles import (
        ProviderPreflightError,
        activated_routes_profile,
        preflight_real_routes,
    )

    if args.real and not args.routes_profile:
        print(
            "erro: matrix-suite --real exige --routes-profile explícito",
            file=sys.stderr,
        )
        return 2
    with activated_routes_profile(args.routes_profile):
        if args.real:
            try:
                proof = preflight_real_routes(
                    min_groq_interval_seconds=args.groq_min_interval,
                )
            except ProviderPreflightError as exc:
                print(f"erro: preflight LLM falhou: {exc}", file=sys.stderr)
                return 2
            providers = sorted({
                event.get("provider") for event in proof.get("events", [])
                if event.get("status") == "success"
            })
            print(
                f"preflight real verde: tiers={proof['tiers']} providers={providers}"
            )
        return _run_matrix_suite(args)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="playtest", description="Harness de playtest agêntico")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="roda campanha(s) de playtest")
    pr.add_argument("--profile", choices=sorted(PROFILES), default=None)
    pr.add_argument(
        "--scenario",
        choices=("recrutamento", "comercio"),
        default=None,
        help="smoke dirigido com pré-condição e oráculo mecânico",
    )
    pr.add_argument(
        "--all",
        action="store_true",
        help=f"roda os {len(PROFILES)} perfis em série",
    )
    pr.add_argument("--turns", type=int, default=50)
    pr.add_argument("--seed", type=int, default=0)
    pr.add_argument("--start-level", type=int, choices=range(1, 21), default=1)
    pr.add_argument("--class", dest="class_name", default=None,
                    help="classe do personagem (nome ou slug, ex.: sangromante); default Devoto do Abismo")
    pr.add_argument("--real", action="store_true", help="usa LLM real (opt-in, consciente de quota/custo)")
    pr.add_argument("--no-invariants", action="store_true", help="desliga os checks de invariante 5.2")
    pr.add_argument("--max-requests", type=int, default=15, help="teto de invokes de LLM (--real); 0 desliga")
    pr.add_argument("--max-cost", type=float, default=0.0, help="teto de custo USD estimado (--real); 0 desliga")
    pr.add_argument(
        "--turn-timeout",
        type=float,
        default=None,
        help=("teto de wall-clock para startup e cada turno; default 120s em "
              "--real e desligado no mock"),
    )
    pr.set_defaults(func=_cmd_run)

    prp = sub.add_parser("report", help="agrega um run em Markdown")
    prp.add_argument("run_id")
    prp.add_argument("--baseline", default=None, help="run_id anterior p/ deltas")
    prp.set_defaults(func=_cmd_report)

    prt = sub.add_parser("transcript", help="transcrito ação→narração por turno (julgar o prompt)")
    prt.add_argument("run_id")
    prt.set_defaults(func=_cmd_transcript)

    pm = sub.add_parser("merchant-suite", help="roda a matriz longa do comerciante")
    pm.add_argument("--turns", type=int, default=200)
    pm.add_argument("--seed", type=int, default=4100)
    pm.add_argument("--real", action="store_true")
    pm.add_argument("--max-requests", type=int, default=0)
    pm.add_argument("--max-cost", type=float, default=0.0)
    pm.add_argument("--turn-timeout", type=float, default=None)
    pm.set_defaults(func=_cmd_merchant_suite)

    px = sub.add_parser("matrix-suite", help="roda a matriz pareada 10x200")
    px.add_argument("--label", choices=("A", "B"), required=True)
    px.add_argument("--turns", type=int, default=200)
    px.add_argument("--real", action="store_true")
    px.add_argument("--max-requests", type=int, default=0)
    px.add_argument("--max-cost", type=float, default=0.0)
    px.add_argument("--turn-timeout", type=float, default=None)
    px.add_argument("--routes-profile", choices=("groq-free",), default=None)
    px.add_argument(
        "--groq-min-interval", type=float, default=12.0,
        help="intervalo mínimo entre tentativas Groq 120b no playtest real",
    )
    px.set_defaults(func=_cmd_matrix_suite)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
