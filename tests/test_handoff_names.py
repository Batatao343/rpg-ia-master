"""Workspace P5: nomes de handoffs/ seguem SPEC-NNN[-papel]-tipo.md (históricos na allowlist)."""

from __future__ import annotations

from scripts import check_handoff_names as lint


def test_every_handoff_name_follows_the_pattern_or_is_legacy():
    assert lint.violations() == []


def test_legacy_allowlist_only_shrinks():
    assert lint.stale_legacy() == [], "renamed/removed historical handoff: drop it from LEGACY"


def test_pattern_accepts_template_names_and_rejects_drift(tmp_path):
    good = ["SPEC-281-sol-review.md", "SPEC-281-astra-independent-review.md",
            "SPEC-281-eval-authoring.md", "SPEC-281-review.md", "SPEC-281-luna-port-review.md"]
    bad = ["SPEC-282-SOL-review.md", "SPEC-283-Astra-review.md", "spec-284-sol-review.md",
           "SPEC-28-sol-review.md", "SPEC-281-sol-notes.md", "REVIEW-281.md"]
    # números distintos: o FS do Windows não diferencia maiúsculas
    for name in good + bad:
        (tmp_path / name).write_text("x", encoding="utf-8")
    assert lint.violations(tmp_path) == sorted(bad)
