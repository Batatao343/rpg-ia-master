"""SPEC-381 R7(b): mediana de 5 execucoes do tempo cumulativo de ``import api`` (-X importtime)."""

from __future__ import annotations

import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def once() -> float:
    env = {**os.environ, "RPG_FORCE_MOCK": "1", "PYTHONUTF8": "1"}
    p = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import api"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
        check=True,
    )
    for line in p.stderr.splitlines():
        m = re.match(r"import time:\s+(\d+)\s+\|\s+(\d+)\s+\|\s+api$", line)
        if m:
            return int(m.group(2)) / 1000
    raise SystemExit("linha de api nao encontrada")


if __name__ == "__main__":
    xs = [once() for _ in range(5)]
    print(f"api cumulative ms: {xs} median={statistics.median(xs):.1f}")
