"""SPEC-381 R14: fonte unica dos arquivos que compoem a API HTTP.

Scanners de fonte (AST/regex) leem ``api_source_text()`` em vez de ``api.py`` isolado: o
``api.py`` foi fatiado em ``api_core.py``, ``api_models.py``, ``api_presenters.py`` e ``routes/*.py``.
``API_FILES`` falha alto se o mesmo nome de funcao de nivel de modulo aparecer em dois arquivos
(varreduras que juntam funcoes num dict por nome sobrescreveriam uma delas em silencio).
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_TOP = ("api.py", "api_core.py", "api_models.py", "api_presenters.py")


def api_files() -> tuple[Path, ...]:
    files = [ROOT / n for n in _TOP if (ROOT / n).exists()]
    files += sorted((ROOT / "routes").glob("*.py")) if (ROOT / "routes").is_dir() else []
    return tuple(files)


def api_rel_files() -> tuple[str, ...]:
    return tuple(p.relative_to(ROOT).as_posix() for p in api_files())


def _check_unique(files: tuple[Path, ...]) -> None:
    seen: dict[str, Path] = {}
    for path in files:
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in seen:
                    raise AssertionError(
                        f"funcao duplicada {node.name}: {seen[node.name]} e {path}"
                    )
                seen[node.name] = path


API_FILES: tuple[Path, ...] = api_files()
_check_unique(API_FILES)


def api_source_text() -> str:
    """Texto concatenado de todos os arquivos da API (substitui ``Path('api.py').read_text()``)."""
    return "\n".join(p.read_text(encoding="utf-8") for p in api_files())
