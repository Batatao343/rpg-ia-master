"""Read a J-V1 trace from stdin, run every gameplay-gate oracle, print the verdict JSON (SPEC-212).

``python -m evals.gameplay_scan < trace.json`` exits 0 when no oracle found a problem, 1 otherwise.
"""

from __future__ import annotations

import json
import sys

from evals.evaluators.gameplay_gate import scan_trace


def main() -> int:
    verdict = scan_trace(json.load(sys.stdin))
    print(json.dumps(verdict, ensure_ascii=True, sort_keys=True))
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
