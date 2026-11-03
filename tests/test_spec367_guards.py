"""SPEC-367 R22/R24: sem flag nova; golden da 330 e specs de e2e existentes intocados; motor intocado."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git")


def _diff_names(*paths: str, filt: str | None = None) -> list[str]:
    if GIT is None or not (ROOT / ".git").exists():
        pytest.skip("sem git")
    base = subprocess.run(
        [GIT, "merge-base", "HEAD", "9efc97a9"], cwd=ROOT, capture_output=True, text=True
    )
    if base.returncode != 0:
        pytest.skip("base da spec indisponível")
    cmd = [GIT, "diff", "--name-only"]
    if filt:
        cmd.append(f"--diff-filter={filt}")
    cmd += [base.stdout.strip(), "HEAD", "--", *paths]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
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
