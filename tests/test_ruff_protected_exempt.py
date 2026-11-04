"""SPEC-388 B: todo .py protegido de eval fica fora das famílias de lint da SPEC-388.

Avaliador congelado tem hash travado; se o lint novo valesse para ele, quem o criou não
conseguiria pousar sem reescrever o avaliador.
"""

from __future__ import annotations

import tomllib
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {"C90", "SIM", "PERF", "C4", "PIE", "RET", "ERA", "BLE"}


def _exempt_globs() -> list[str]:
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pfi = cfg["tool"]["ruff"]["lint"]["extend-per-file-ignores"]
    return [glob for glob, codes in pfi.items() if FAMILIES <= set(codes)]


def _protected_py() -> list[str]:
    out = []
    for line in (ROOT / "evals" / "protected-paths.txt").read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        path = ROOT / entry
        if entry.endswith(".py"):
            out.append(entry)
        elif path.is_dir():
            out += [p.relative_to(ROOT).as_posix() for p in path.rglob("*.py")]
    return out


def test_protected_python_files_are_exempt_from_spec388_families() -> None:
    globs = _exempt_globs()
    uncovered = [p for p in _protected_py() if not any(fnmatch(p, g) for g in globs)]
    assert uncovered == [], (
        f"adicione um glob em [tool.ruff.lint.extend-per-file-ignores]: {uncovered}"
    )
