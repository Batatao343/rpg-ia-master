"""SPEC-364 R26/R27: golden da SPEC-330 intocado, orquestrador/cenas intactos, nenhuma flag nova.

Guard de branch: vale enquanto a branch da spec (`spec-364`) esta checada; depois do pouso na `main`
nao ha o que comparar (outras specs podem mudar esses arquivos com seu proprio gate)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = "cb02071d"  # `main` sobre a qual a SPEC-364 foi escrita
PROTECTED = (
    "tests/spec330_equivalence.py",
    "tests/fixtures/spec330_legacy_golden.json",
    "services/conflict_orchestrator.py",
    "services/scene_cards.py",
    "config/flags.yaml",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout.strip()


def test_golden_and_engine_untouched_since_base():
    if _git("rev-parse", "--abbrev-ref", "HEAD") != "spec-364":
        pytest.skip("guard so vale na branch spec-364")
    assert _git("rev-parse", "--verify", "-q", f"{BASE}^{{commit}}"), "commit base ausente"
    diff = _git("diff", "--name-only", BASE, "HEAD", "--", *PROTECTED)
    assert diff == "", f"arquivo protegido da SPEC-364 mudou: {diff}"
