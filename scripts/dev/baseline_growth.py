"""Relatório de crescimento de baselines (SPEC-416 R29). Somente leitura.

Compara `git show <base>:<arquivo>` com o worktree em `tests/size_budget.json`,
`tests/clock_asserts.json`, `ruff-baseline-counts.json` e os pares de `ruff-baseline.toml`;
lista chave nova ou valor que subiu e sai com rc 1 se houver alguma. Pega também edição à mão
do JSON, que o hook de subagente não vê. O coordenador roda no pouso (`land_check`).

    bash scripts/dev/py.sh scripts/dev/baseline_growth.py [--base main]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_FILES = {
    "tests/size_budget.json": ("files", "functions"),
    "tests/clock_asserts.json": ("functions",),
    "ruff-baseline-counts.json": ("counts",),
}
TOML_FILE = "ruff-baseline.toml"


def _base_text(root: Path, base: str, rel: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), "show", f"{base}:{rel}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return out.stdout if out.returncode == 0 else ""


def _flatten(data: dict, prefix: str = "") -> dict[str, int]:
    flat: dict[str, int] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}::"))
        elif isinstance(value, int):
            flat[f"{prefix}{key}"] = value
    return flat


def _json_view(text: str, sections: tuple[str, ...]) -> dict[str, int]:
    data = json.loads(text) if text.strip() else {}
    return _flatten({s: data.get(s, {}) for s in sections})


def _toml_view(text: str) -> dict[str, int]:
    table = tomllib.loads(text)["lint"]["per-file-ignores"] if text.strip() else {}
    return {f"{f}::{c}": 1 for f, codes in table.items() for c in codes}


def growth(old: dict[str, int], new: dict[str, int], label: str) -> list[str]:
    found = []
    for key, value in sorted(new.items()):
        if key not in old:
            found.append(f"{label}: chave nova {key} ({value})")
        elif value > old[key]:
            found.append(f"{label}: subiu {key} {old[key]} -> {value}")
    return found


def report(root: Path, base: str, ignore_new_files: bool = False) -> list[str]:
    found: list[str] = []
    for rel, sections in JSON_FILES.items():
        if ignore_new_files and not _base_text(root, base, rel):
            continue
        path = root / rel
        new = _json_view(path.read_text(encoding="utf-8"), sections) if path.is_file() else {}
        found += growth(_json_view(_base_text(root, base, rel), sections), new, rel)
    toml_path = root / TOML_FILE
    new_toml = _toml_view(toml_path.read_text(encoding="utf-8")) if toml_path.is_file() else {}
    found += growth(_toml_view(_base_text(root, base, TOML_FILE)), new_toml, TOML_FILE)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="main")
    parser.add_argument(
        "--ignore-new-files",
        action="store_true",
        help="baseline ausente na base = criação, não crescimento",
    )
    args = parser.parse_args(argv)
    found = report(ROOT, args.base, args.ignore_new_files)
    print("\n".join(found) if found else "nenhum baseline cresceu")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
