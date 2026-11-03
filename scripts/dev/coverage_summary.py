"""SPEC-379 R1.5: resume um `coverage.json` em Markdown (modulos menos cobertos + total).

Uso: python scripts/dev/coverage_summary.py coverage.json --top 20 [--min-statements K]
Saida deterministica: ordem crescente de % de linhas, desempate pelo caminho.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _pct(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered * 100.0 / total


def _row(path: str, summary: dict) -> dict:
    lines_total = int(summary.get("num_statements", 0))
    lines_cov = int(summary.get("covered_lines", 0))
    br_total = int(summary.get("num_branches", 0))
    br_cov = int(summary.get("covered_branches", 0))
    return {
        "path": path,
        "lines": lines_total,
        "lines_pct": _pct(lines_cov, lines_total),
        "branches": br_total,
        "branches_pct": _pct(br_cov, br_total),
    }


def build_rows(data: dict, min_statements: int = 0) -> list[dict]:
    rows = [_row(p, f.get("summary", {})) for p, f in (data.get("files") or {}).items()]
    rows = [r for r in rows if r["lines"] >= min_statements]
    return sorted(rows, key=lambda r: (r["lines_pct"], r["path"]))


def render(data: dict, top: int = 20, min_statements: int = 0) -> str:
    rows = build_rows(data, min_statements)[: max(0, top)]
    out = [
        "| modulo | linhas | % linhas | ramos | % ramos |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        out.append(
            f"| {r['path']} | {r['lines']} | {r['lines_pct']:.1f} | "
            f"{r['branches']} | {r['branches_pct']:.1f} |"
        )
    total = _row("TOTAL", data.get("totals", {}))
    out.append(
        f"| **TOTAL** | {total['lines']} | {total['lines_pct']:.1f} | "
        f"{total['branches']} | {total['branches_pct']:.1f} |"
    )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coverage_json")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-statements", type=int, default=0)
    args = parser.parse_args(argv)
    path = Path(args.coverage_json)
    if not path.exists():
        print(f"coverage_summary: {path} nao existe", file=sys.stderr)
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    sys.stdout.write(render(data, args.top, args.min_statements))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
