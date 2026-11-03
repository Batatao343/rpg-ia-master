"""SPEC-379 R1.5: resumo Markdown de coverage.json."""

from __future__ import annotations

import json

from scripts.dev import coverage_summary as cs


def _file(stmts, cov, br, brcov):
    return {
        "summary": {
            "num_statements": stmts,
            "covered_lines": cov,
            "num_branches": br,
            "covered_branches": brcov,
        }
    }


DATA = {
    "files": {
        "b.py": _file(10, 5, 4, 2),
        "a.py": _file(10, 5, 2, 1),
        "c.py": _file(20, 20, 0, 0),
        "tiny.py": _file(2, 0, 0, 0),
    },
    "totals": {
        "num_statements": 42,
        "covered_lines": 30,
        "num_branches": 6,
        "covered_branches": 3,
    },
}


def _paths(md: str) -> list[str]:
    return [ln.split("|")[1].strip() for ln in md.splitlines()[2:]]


def test_ascending_order_with_path_tiebreak_and_total():
    md = cs.render(DATA, top=10)
    assert _paths(md) == ["tiny.py", "a.py", "b.py", "c.py", "**TOTAL**"]
    assert md.splitlines()[-1].startswith("| **TOTAL** | 42 | 71.4 | 6 | 50.0 |")


def test_top_and_min_statements():
    assert _paths(cs.render(DATA, top=2)) == ["tiny.py", "a.py", "**TOTAL**"]
    assert "tiny.py" not in cs.render(DATA, top=10, min_statements=5)


def test_output_is_deterministic(tmp_path, capsys):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(DATA), encoding="utf-8")
    assert cs.main([str(path), "--top", "3"]) == 0
    first = capsys.readouterr().out
    assert cs.main([str(path), "--top", "3"]) == 0
    assert capsys.readouterr().out == first


def test_missing_file_fails(tmp_path):
    assert cs.main([str(tmp_path / "nope.json")]) == 1
