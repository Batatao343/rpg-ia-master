"""SPEC-317 R12 — excludeFiles não pode tirar nada que o runtime lê."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _globs() -> list[str]:
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    return cfg["functions"]["vercel_app.py"]["excludeFiles"].strip("{}").split(",")


def test_dead_weight_is_excluded():
    globs = _globs()
    for glob in ("lore_nova/**", "handoffs/**", "project_index/**", "tests/**", "docs/**"):
        assert glob in globs


def test_runtime_read_paths_are_not_excluded():
    globs = _globs()
    # discovery.codex_body lê data/codex/*.md em runtime; os índices FAISS e os JSONs
    # de dados são lidos por rag/gamedata; evals.* é importado por jev_rollout.
    for needed in (
        "data/**",
        "data/codex/**",
        "faiss_lore_index/**",
        "faiss_rules_index/**",
        "assets/**",
        "services/**",
        "agents/**",
        "evals/**",
        "evals/core/**",
        "evals/evaluators/**",
        "evals/experiments/**",
    ):
        assert needed not in globs, needed


def test_codex_markdown_is_read_at_runtime():
    # Guarda da decisão D5: se o runtime deixar de ler o codex, esta asserção cai e a
    # exclusão de data/codex/** pode ser reavaliada.
    source = (ROOT / "services" / "discovery.py").read_text(encoding="utf-8")
    assert "codex_body(" in source
