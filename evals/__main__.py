"""Command line interface for deterministic component evals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.core.compare import compare_runs
from evals.core.governance import GovernanceError
from evals.core.runner import EvalRunnerError, run_eval, write_run
from evals.core.schemas import EvalRunResult


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


def _error_rows(result: EvalRunResult) -> list[dict[str, str]]:
    """Case id + exception class only; the message may carry dataset content."""

    rows: list[dict[str, str]] = []
    for case_id in result.error_case_ids:
        first = (result.case_diagnostics.get(case_id) or [""])[0]
        rows.append({"case_id": case_id, "error_type": first.split(":", 1)[0] or "Exception"})
    return rows


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
                        "errors": _error_rows(result),
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
