"""Orçamento de tamanho (SPEC-386 R6): god-file e função gigante não crescem.

Arquivo de código > FILE_LIMIT linhas e função Python > FUNC_LIMIT linhas só passam se
estiverem em `tests/size_budget.json`, e nunca acima do valor registrado. Encolher é livre;
item que caiu abaixo do limite some da baseline no próximo `--update`.

    bash scripts/dev/py.sh scripts/dev/size_budget.py            # confere (rc 1 se estourou)
    bash scripts/dev/py.sh scripts/dev/size_budget.py --update   # regrava a baseline

Estourou? Extraia o código novo para um módulo próprio. Exceção justificada = `--update`
no mesmo commit, com o motivo na mensagem (o revisor rejeita crescimento sem motivo).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "tests" / "size_budget.json"
FILE_LIMIT = 1000
FUNC_LIMIT = 100
PATTERNS = ("*.py", "web/src/*.ts", "web/src/*.tsx")
SKIP_PREFIXES = ("tests/", "web/e2e/", "evals/", "playtest_runs/", "docs/", "data/")


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", *PATTERNS],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    return sorted(p for p in out.splitlines() if p and not p.startswith(SKIP_PREFIXES))


def _functions(tree: ast.AST, prefix: str = ""):
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            name = f"{prefix}{node.name}"
            yield name, node.end_lineno - node.lineno + 1
            yield from _functions(node, f"{name}.")
        elif isinstance(node, ast.ClassDef):
            yield from _functions(node, f"{prefix}{node.name}.")


def measure(root: Path, files: list[str]) -> dict[str, dict[str, int]]:
    """Itens acima do limite: {"files": {path: linhas}, "functions": {path::qual: linhas}}."""
    big_files: dict[str, int] = {}
    big_funcs: dict[str, int] = {}
    for rel in files:
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
        if lines > FILE_LIMIT:
            big_files[rel] = lines
        if rel.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for name, size in _functions(tree):
                if size > FUNC_LIMIT:
                    big_funcs[f"{rel}::{name}"] = size
    return {"files": big_files, "functions": big_funcs}


def problems(current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]) -> list[str]:
    found = []
    limits = {"files": FILE_LIMIT, "functions": FUNC_LIMIT}
    for kind, items in current.items():
        known = baseline.get(kind, {})
        for key, size in sorted(items.items()):
            if key not in known:
                found.append(f"{kind[:-1]} novo acima de {limits[kind]} linhas: {key} ({size})")
            elif size > known[key]:
                found.append(
                    f"{kind[:-1]} cresceu: {key} {known[key]} -> {size} (+{size - known[key]})"
                )
    return found


def load_baseline(path: Path = BASELINE) -> dict[str, dict[str, int]]:
    if not path.is_file():
        return {"files": {}, "functions": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"files": data.get("files", {}), "functions": data.get("functions", {})}


def write_baseline(current: dict[str, dict[str, int]], path: Path = BASELINE) -> None:
    data = {
        "_doc": "Gerado por scripts/dev/size_budget.py --update (SPEC-386). Só encolhe; crescer exige motivo no commit.",
        "limits": {"file": FILE_LIMIT, "function": FUNC_LIMIT},
        "files": dict(sorted(current["files"].items())),
        "functions": dict(sorted(current["functions"].items())),
    }
    path.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args(argv)
    current = measure(ROOT, tracked_files(ROOT))
    if args.update:
        write_baseline(current)
        print(f"{len(current['files'])} arquivos e {len(current['functions'])} funções na baseline")
        return 0
    found = problems(current, load_baseline())
    for line in found:
        print(line)
    if found:
        print(
            "Extraia o código novo para um módulo próprio (ver docstring de scripts/dev/size_budget.py)."
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
