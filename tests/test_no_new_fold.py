"""SPEC-388 Etapa C: fold de texto tem um dono só, `services.text.fold` (SPEC-378).

Falha se aparecer `def _fold*`, `def _norm` ou `def _norm_*` novo fora de `services/text.py`.
As cópias que a SPEC-378 manteve estão em `tests/data/fold_allowlist.txt`, que só encolhe.
Precisa de um fold diferente? Use os parâmetros de `fold` (case/strip/collapse) ou justifique
na spec e acrescente a linha com o motivo no commit.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "tests" / "data" / "fold_allowlist.txt"
DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(_fold\w*|_norm|_norm_\w+)\s*\(", re.M)
SKIP = ("tests/", "evals/", "playtest_runs/", "docs/", "data/")
OWNER = "services/text.py"


def _found() -> set[str]:
    files = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--", "*.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.splitlines()
    out = set()
    for rel in files:
        if rel.startswith(SKIP) or rel == OWNER:
            continue
        text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        out |= {f"{rel}::{name}" for name in DEF_RE.findall(text)}
    return out


def _allowed() -> set[str]:
    lines = ALLOWLIST.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def test_no_new_local_fold() -> None:
    new = sorted(_found() - _allowed())
    assert not new, "fold local novo; use services.text.fold:\n" + "\n".join(new)


def test_fold_allowlist_only_shrinks() -> None:
    stale = sorted(_allowed() - _found())
    assert not stale, "remova da allowlist (já migrados):\n" + "\n".join(stale)
