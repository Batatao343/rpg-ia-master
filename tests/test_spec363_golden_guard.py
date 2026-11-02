"""SPEC-363 R47: golden da 330 intocado; o motor (resolve_turn / reação) não foi tocado por esta spec."""

from __future__ import annotations

import subprocess


def _clean_against_main(*paths: str) -> bool:
    return (
        subprocess.run(
            ["git", "diff", "--quiet", "main", "--", *paths], capture_output=True, check=False
        ).returncode
        == 0
    )


def test_golden_files_have_no_diff_against_main():
    assert _clean_against_main(
        "tests/spec330_equivalence.py", "tests/fixtures/spec330_legacy_golden.json"
    )


def test_engine_modules_untouched_by_spec363():
    # R14/R15 leem `final_blows` (já gravado pelo orquestrador); nada novo dentro do motor.
    assert _clean_against_main("services/conflict_orchestrator.py", "services/conflict_turn.py")
