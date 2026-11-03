"""SPEC-387 R38-R40: sem flag nova; golden da 330, avaliador/sim/promote/lint e e2e existentes intocados.

Guarda de pouso: só vale na branch `spec-387` (depois do pouso outras specs mexem nesses arquivos)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([GIT or "git", *args], cwd=ROOT, capture_output=True, text=True)


def _diff_names(*paths: str, filt: str | None = None) -> list[str]:
    if GIT is None or not (ROOT / ".git").exists():
        pytest.skip("sem git")
    if _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "spec-387":
        pytest.skip("guarda da SPEC-387: só na branch spec-387")
    base = _git("merge-base", "main", "HEAD").stdout.strip()
    if not base:
        pytest.skip("merge-base com a main indisponível")
    cmd = ["diff", "--name-only"]
    if filt:
        cmd.append(f"--diff-filter={filt}")
    out = _git(*cmd, base, "HEAD", "--", *paths)
    return [x for x in out.stdout.splitlines() if x.strip()]


def test_no_new_flag():
    assert _diff_names("config/flags.yaml", "scripts/staging/staging_flags.json") == []


def test_golden_330_and_evals_untouched():
    assert (
        _diff_names(
            "tests/spec330_equivalence.py", "tests/fixtures/spec330_legacy_golden.json", "evals"
        )
        == []
    )


def test_gate_scripts_and_budget_untouched():
    assert (
        _diff_names(
            "scripts/cards/lint.py",
            "scripts/cards/sim.py",
            "scripts/cards/promote.py",
            "data/cards/_orcamento.json",
        )
        == []
    )


def test_existing_e2e_specs_not_modified():
    assert _diff_names("web/e2e", filt="MDR") == []
