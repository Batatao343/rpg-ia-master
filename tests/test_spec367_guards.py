"""SPEC-367 R22/R24: sem flag nova; golden da 330 e specs de e2e existentes intocados; motor intocado."""

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
    """Guarda de pouso: só vale na branch da spec (fora dela, depois do pouso, `skip`)."""
    if GIT is None or not (ROOT / ".git").exists():
        pytest.skip("sem git")
    if _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "spec-367":
        pytest.skip("guarda da SPEC-367: só na branch spec-367")
    base = _git("merge-base", "main", "HEAD").stdout.strip()
    if not base:
        pytest.skip("merge-base com a main indisponível")
    cmd = ["diff", "--name-only"]
    if filt:
        cmd.append(f"--diff-filter={filt}")
    out = _git(*cmd, f"{base}", "HEAD", "--", *paths)
    return [x for x in out.stdout.splitlines() if x.strip()]


def test_no_new_flag():
    assert _diff_names("config/flags.yaml") == []


def test_golden_330_untouched():
    assert (
        _diff_names("tests/spec330_equivalence.py", "tests/fixtures/spec330_legacy_golden.json")
        == []
    )


def test_existing_e2e_specs_not_modified():
    assert _diff_names("web/e2e", filt="MDR") == []


def test_engine_untouched():
    assert (
        _diff_names(
            "services/conflict_orchestrator.py",
            "services/scene_cards.py",
            "services/conflict_turn.py",
        )
        == []
    )
