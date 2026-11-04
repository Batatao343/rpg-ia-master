"""SPEC-381 R14: contagens que os scanners de fonte veem, no commit-base (``--ref``) e na ponta.

``python scripts/dev/api_scanner_counts.py [--ref <git-ref>]``: sem ``--ref`` le os arquivos da API
do worktree (``api.py`` + ``api_*.py`` + ``routes/*.py``); com ``--ref`` le ``api.py`` daquele commit.
As contagens (itens varridos / achados) tem de ser iguais antes e depois do fatiamento.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _text(ref: str | None) -> str:
    if ref:
        return subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{ref}:api.py"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
    files = [ROOT / n for n in ("api.py", "api_core.py", "api_models.py", "api_presenters.py")]
    files += sorted((ROOT / "routes").glob("*.py")) if (ROOT / "routes").is_dir() else []
    return "\n".join(p.read_text(encoding="utf-8") for p in files if p.exists())


def counts(text: str) -> dict[str, int]:
    tree = ast.parse(text)
    fns = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return {
        "functions": len(fns),
        "http_exception_calls": len(
            [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "HTTPException"
            ]
        ),
        "except_handlers": len([n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]),
        "status_429_413_calls": len(
            [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and n.args
                and isinstance(n.args[0], ast.Constant)
                and n.args[0].value in (429, 413)
            ]
        ),
        "codes_503": len(re.findall(r"HTTPException\(\s*503,\s*(?:detail=)?\"([a-z_]+)\"", text)),
        "admin_connection_calls": text.count("admin_connection("),
        "with_structured_output": text.count("with_structured_output("),
        "enforce_owner_budget_calls": len(
            [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_enforce_owner_budget"
            ]
        ),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref")
    a = ap.parse_args()
    print(json.dumps(counts(_text(a.ref)), indent=1, sort_keys=True))
