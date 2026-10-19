"""SPEC-250 R4: varredura AST de ``except`` amplo que degrada sem deixar rastro.

Usada por ``tests/test_no_silent_except.py`` e por ``scripts`` de manutencao da allowlist.
Um handler ``except Exception|BaseException|<bare>`` e SILENCIOSO quando seu corpo nao relanca
(``raise``) e nao contem chamada de log/metrica, e a linha do ``except`` (ou a anterior) nao traz
``# silent-ok: <motivo>``.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("agents", "services", "infrastructure", "workers")
SCAN_FILES = ("api.py", "llm_setup.py", "rag.py", "persistence.py")


def _is_broad(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    names = []
    for node in (t.elts if isinstance(t, ast.Tuple) else [t]):
        names.append(node.id if isinstance(node, ast.Name) else getattr(node, "attr", ""))
    return any(n in {"Exception", "BaseException"} for n in names)


def _call_name(call: ast.Call) -> str:
    parts = []
    node = call.func
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(_call_name(node))
    return ".".join(reversed(parts))


def _logs_or_raises(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            name = _call_name(node).lower()
            if ("log" in name or "metrics.increment" in name or name.endswith("warn")
                    or "fallback" in name):
                return True
    return False


def scan() -> list[str]:
    """Chaves ``arquivo::funcao::n`` (n = ordem do handler silencioso na funcao)."""
    files: list[Path] = []
    for d in SCAN_DIRS:
        files += sorted((ROOT / d).rglob("*.py"))
    files += [ROOT / f for f in SCAN_FILES]
    keys: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        tree = ast.parse(text)
        rel = path.relative_to(ROOT).as_posix()

        def visit(node: ast.AST, scope: str, counters: dict) -> None:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, f"{scope}.{child.name}" if scope else child.name, counters)
                    continue
                if isinstance(child, ast.ExceptHandler) and _is_broad(child) and not _logs_or_raises(child):
                    around = " ".join(lines[max(0, child.lineno - 2):child.lineno])
                    if "silent-ok" not in around:
                        counters[scope] = counters.get(scope, 0) + 1
                        keys.append(f"{rel}::{scope or '<module>'}::{counters[scope]}")
                visit(child, scope, counters)

        visit(tree, "", {})
    return keys
