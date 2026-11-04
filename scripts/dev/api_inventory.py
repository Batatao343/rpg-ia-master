"""SPEC-381 R13: inventario (AST) de tudo que toca ``api.<nome>`` fora de ``api.py``.

Uso: ``bash scripts/dev/py.sh scripts/dev/api_inventory.py [--out docs/spec381/patch_inventory.json]``.
Cada entrada: ``{file, line, name, kind}`` com ``kind`` em
``setattr | string | from_import | read | attr_object | reload``.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (
    "tests",
    "playtest",
    "evals",
    "scripts",
    "services",
    "workers",
    "infrastructure",
    "observability",
)
ROOT_FILES_EXCLUDE = {"api.py"}
BASE_ALIASES = {"api", "api_mod", "api_module"}


def _aliases(tree: ast.AST) -> set[str]:
    out = set(BASE_ALIASES)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "api" and a.asname:
                    out.add(a.asname)
    return out


def scan_tree(tree: ast.AST, rel: str) -> list[dict]:  # noqa: C901
    al = _aliases(tree)
    rows: list[dict] = []
    parents: dict[int, ast.AST] = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            parents[id(c)] = p

    def row(n: ast.AST, name: str, kind: str) -> None:
        rows.append({"file": rel, "line": n.lineno, "name": name, "kind": kind})

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "api" and n.level == 0:
            for a in n.names:
                row(n, a.name, "from_import")
        elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in al:
            par = parents.get(id(n))
            if isinstance(par, ast.Attribute) and par.value is n:
                kind = "attr_object"
            elif n.attr == "reload":
                kind = "read"
            else:
                kind = "read"
            row(n, n.attr, kind)
        elif isinstance(n, ast.Call):
            fn = n.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if fname == "setattr" and n.args:
                a0 = n.args[0]
                if isinstance(a0, ast.Name) and a0.id in al and len(n.args) > 1:
                    a1 = n.args[1]
                    if isinstance(a1, ast.Constant) and isinstance(a1.value, str):
                        row(n, a1.value, "setattr")
                elif (
                    isinstance(a0, ast.Constant)
                    and isinstance(a0.value, str)
                    and a0.value.startswith("api.")
                ):
                    row(n, a0.value.split(".")[1], "string")
            elif (
                fname == "reload"
                and n.args
                and isinstance(n.args[0], ast.Name)
                and n.args[0].id in al
            ):
                row(n, "reload", "reload")
    return rows


def scan_all() -> list[dict]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        files += sorted((ROOT / d).rglob("*.py"))
    files += [p for p in sorted(ROOT.glob("*.py")) if p.name not in ROOT_FILES_EXCLUDE]
    rows: list[dict] = []
    for p in files:
        if ".venv" in p.parts or p.name == "api_inventory.py":
            continue
        rel = p.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rows += scan_tree(tree, rel)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = scan_all()
    if a.out:
        Path(a.out).write_text(
            json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(len(rows), "rows;", len({r["file"] for r in rows}), "files")
    print("setattr names:", sorted({r["name"] for r in rows if r["kind"] in ("setattr", "string")}))
