"""SPEC-406 R1: a superficie de ``api`` lida por consumidores de fora existe.

O ruff so enxerga uso dentro de ``api.py``; quem le ``api.<nome>`` ou ``from api import <nome>``
em testes, playtest, evals e scripts fica invisivel para ele. Este teste percorre esses
consumidores por AST e exige ``hasattr(api, nome)``.

Limites: nao ve ``getattr`` com nome computado nem modulo carregado por ``importlib`` dinamico
(cobertos por ``patch_liveness`` e pelos testes do escopo).
"""

from __future__ import annotations

import ast
from pathlib import Path

import api

ROOT = Path(__file__).resolve().parents[1]
_DIRS = ("tests", "playtest", "evals", "scripts", "services", "routes", "agents", "infrastructure", "observability")


def _consumer_files() -> list[Path]:
    files = [p for d in _DIRS for p in (ROOT / d).rglob("*.py")]
    files += [p for p in ROOT.glob("*.py") if p.name != "api.py"]
    return sorted(files)


def _api_aliases(tree: ast.AST) -> set[str]:
    """Nomes locais que apontam para o modulo ``api`` (so conta quem de fato o importa)."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {a.asname or "api" for a in node.names if a.name == "api"}
    return aliases


def _reads(path: Path) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    aliases = _api_aliases(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in aliases:
                found.append((node.lineno, node.attr))
        elif isinstance(node, ast.ImportFrom) and node.module == "api" and node.level == 0:
            found.extend((node.lineno, a.name) for a in node.names if a.name != "*")
        elif isinstance(node, ast.Call) and len(node.args) >= 2:
            first, second = node.args[0], node.args[1]
            if isinstance(first, ast.Name) and first.id in aliases:
                if isinstance(second, ast.Constant) and isinstance(second.value, str):
                    found.append((node.lineno, second.value))
    return found


def _all_reads() -> dict[str, list[str]]:
    reads: dict[str, list[str]] = {}
    for path in _consumer_files():
        for line, name in _reads(path):
            reads.setdefault(name, []).append(f"{path.relative_to(ROOT).as_posix()}:{line}")
    return reads


def test_api_attributes_read_by_consumers_exist():
    missing = [f"{where} {name}" for name, wheres in _all_reads().items() if not hasattr(api, name) for where in wheres]
    assert not missing, "consumidores leem atributo ausente de api:\n" + "\n".join(sorted(missing))


def test_scanner_sees_known_reads():
    reads = _all_reads()
    for name in ("format_response", "_npcs_block", "app", "health_check"):
        assert reads.get(name), f"scanner nao encontrou nenhuma leitura de api.{name}"
