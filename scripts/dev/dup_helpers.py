"""Radar de helper duplicado (SPEC-386 R7). Só leitura, sem LLM.

    bash scripts/dev/py.sh scripts/dev/dup_helpers.py --diff main...HEAD   # revisão de spec
    bash scripts/dev/py.sh scripts/dev/dup_helpers.py --top 30             # panorama do repo

`--diff`: funções adicionadas no diff cujo nome já é definido em outro módulo de produção.
Sem `--diff`: nomes definidos em 3+ módulos (candidatos a helper único, ex.: `_fold`).
Nome igual não prova duplicação; é a lista do que o revisor deve abrir.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.M)
SKIP_PREFIXES = ("tests/", "evals/", "playtest_runs/", "docs/", "data/")
GENERIC = {
    "main",
    "run",
    "_run",
    "build",
    "parse_args",
    "setup",
    "teardown",
    "invoke",
    "get",
    "load",
    "save",
    "wrapper",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout


def definitions() -> dict[str, set[str]]:
    where: dict[str, set[str]] = defaultdict(set)
    for rel in _git("ls-files", "--", "*.py").splitlines():
        if rel.startswith(SKIP_PREFIXES):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name in DEF_RE.findall(text):
            if not (name.startswith("__") or name in GENERIC or name.startswith("test_")):
                where[name].add(rel)
    return where


def added_defs(rev: str) -> dict[str, set[str]]:
    added: dict[str, set[str]] = defaultdict(set)
    current = ""
    for line in _git("diff", "--unified=0", rev, "--", "*.py").splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif (
            line.startswith("+")
            and not line.startswith("+++")
            and not current.startswith(SKIP_PREFIXES)
        ):
            m = DEF_RE.match(line[1:])
            if m and not m.group(1).startswith("__"):
                added[m.group(1)].add(current)
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--diff", metavar="REV", help="ex.: main...HEAD")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args(argv)
    where = definitions()
    if args.diff:
        hits = []
        for name, files in sorted(added_defs(args.diff).items()):
            others = sorted(where.get(name, set()) - files)
            if others:
                hits.append(
                    f"{name} (novo em {', '.join(sorted(files))}) já existe em: {', '.join(others[:5])}"
                )
        print("\n".join(hits) if hits else "nenhuma função nova com nome já usado em outro módulo")
        return 0
    ranked = sorted(((len(f), n) for n, f in where.items() if len(f) >= 3), reverse=True)
    for count, name in ranked[: args.top]:
        print(f"{count:3d}  {name}  ({', '.join(sorted(where[name])[:3])}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
