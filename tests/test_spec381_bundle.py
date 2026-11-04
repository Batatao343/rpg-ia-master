"""SPEC-381 R15/R16: os modulos novos entram no bundle da Vercel e nos gates por caminho."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from scripts import ci_eval_scope
from scripts.dev import eval_publish

ROOT = Path(__file__).resolve().parents[1]
NEW = ["routes/__init__.py", "routes/turn.py", "api_core.py", "api_models.py", "api_presenters.py"]


def _exclude_globs() -> list[str]:
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    raw = cfg["functions"]["vercel_app.py"]["excludeFiles"].strip("{}")
    return [g for g in raw.split(",") if g]


def test_vercel_exclude_globs_do_not_match_new_modules():
    for path in NEW:
        assert not any(fnmatch.fnmatch(path, g) for g in _exclude_globs()), path


def test_vercelignore_does_not_list_new_modules():
    lines = [
        ln.strip().rstrip("/")
        for ln in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    for path in NEW:
        assert not any(path == ln or path.startswith(ln + "/") for ln in lines), path


def test_path_gates_know_the_new_modules():
    for path in ["routes/turn.py", "api_core.py", "api_models.py", "api_presenters.py"]:
        scope = ci_eval_scope.classify([path], ROOT / "evals/protected-paths.txt")
        assert scope["frontend"], path
        assert path in eval_publish.PRODUCT_FILES or path.startswith(eval_publish.PRODUCT_PREFIXES)
