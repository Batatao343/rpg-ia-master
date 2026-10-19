"""SPEC-222 R1: nenhum ``print()`` em código de produção.

stdout de função serverless vira log da plataforma, fora de ``safe_json``/redaction.
Permitidos: ``scripts/``, ``playtest/``, ``evals/``, ``tests/``, o CLI ``game_engine.py``
e blocos ``if __name__ == "__main__":``.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_DIRS = ("agents", "services", "infrastructure", "observability", "workers")
ALLOWED_ROOT_FILES = {"game_engine.py", "conftest.py"}


def _production_files() -> list[Path]:
    files = [p for p in ROOT.glob("*.py") if p.name not in ALLOWED_ROOT_FILES]
    for folder in PRODUCTION_DIRS:
        files.extend((ROOT / folder).rglob("*.py"))
    return sorted(files)


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    names = [test.left, *test.comparators]
    return any(isinstance(n, ast.Name) and n.id == "__name__" for n in names) and any(
        isinstance(n, ast.Constant) and n.value == "__main__" for n in names
    )


def _prints(tree: ast.Module) -> list[int]:
    skip: set[int] = set()
    for node in tree.body:
        if _is_main_guard(node):
            skip.update(id(child) for child in ast.walk(node))
    return [
        node.lineno
        for node in ast.walk(tree)
        if id(node) not in skip
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def test_production_code_has_no_print_calls():
    offenders = []
    for path in _production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(f"{path.relative_to(ROOT).as_posix()}:{line}" for line in _prints(tree))
    assert not offenders, "print() em produção (use logging rpg.* + safe_json):\n" + "\n".join(
        offenders
    )


def test_guard_detects_print_outside_main():
    tree = ast.parse("print('x')\nif __name__ == '__main__':\n    print('ok')\n")
    assert _prints(tree) == [1]
