"""Command line interface for deterministic component evals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.core.compare import compare_runs
from evals.core.governance import GovernanceError
from evals.core.runner import EvalRunnerError, run_eval, write_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run")
    run.add_argument("--dataset", action="append", default=[])
    run.add_argument("--case", action="append", default=[])
    run.add_argument("--suite", action="append", default=[])
    run.add_argument("--tag", action="append", default=[])
    run.add_argument("--seed", type=int, default=7)
    run.add_argument("--run-id")
    run.add_argument("--output", type=Path)

    compare = subcommands.add_parser("compare")
    compare.add_argument("--current", type=Path, required=True)
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.root.resolve()
    try:
        if args.command == "run":
            result = run_eval(
                root,
                datasets=args.dataset or None,
                case_ids=set(args.case) or None,
                suites=set(args.suite) or None,
                tags=set(args.tag) or None,
                seed=args.seed,
                run_id=args.run_id,
            )
            output = args.output or root / "evals/runs"
            json_path, markdown_path = write_run(result, output)
            print(
                json.dumps(
                    {
                        "run_id": result.run_id,
                        "passed": result.passed,
                        "json": str(json_path),
                        "markdown": str(markdown_path),
                        "metrics": result.metric_values,
                        "aggregates": result.aggregates,
                        "hard_failures": result.hard_failures,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0 if result.passed else 1

        comparison = compare_runs(root, args.current, args.baseline)
        encoded = json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0 if comparison["passed"] else 1
    except (GovernanceError, EvalRunnerError, ValueError) as error:
        print(f"eval failed closed: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
