"""SPEC-386 R6: god-file e função gigante não crescem (baseline em tests/size_budget.json)."""

from __future__ import annotations

from pathlib import Path

from scripts.dev import size_budget as sb


def test_repo_respects_size_budget() -> None:
    current = sb.measure(sb.ROOT, sb.tracked_files(sb.ROOT))
    found = sb.problems(current, sb.load_baseline())
    assert not found, "\n".join(
        [
            *found,
            "Extraia o código novo para módulo próprio; encolheu = size_budget.py --tighten;"
            " exceção = size_budget.py --update + motivo no commit.",
        ]
    )


def _py(lines: int, func_lines: int) -> str:
    body = "\n".join(f"    x{i} = {i}" for i in range(func_lines - 1))
    filler = "\n".join(f"y{i} = {i}" for i in range(max(0, lines - func_lines)))
    return f"def big():\n{body}\n{filler}\n"


def test_growth_and_new_offenders_fail(tmp_path: Path) -> None:
    (tmp_path / "god.py").write_text(_py(sb.FILE_LIMIT + 50, 20), encoding="utf-8")
    (tmp_path / "fn.py").write_text(_py(10, sb.FUNC_LIMIT + 5), encoding="utf-8")
    current = sb.measure(tmp_path, ["god.py", "fn.py"])
    assert current["files"] == {"god.py": sb.FILE_LIMIT + 50}
    assert current["functions"] == {"fn.py::big": sb.FUNC_LIMIT + 5}

    assert len(sb.problems(current, {"files": {}, "functions": {}})) == 2  # novos sem baseline
    assert sb.problems(current, current) == []  # igual à baseline
    grown = {"files": {"god.py": sb.FILE_LIMIT + 10}, "functions": current["functions"]}
    assert sb.problems(current, grown) == [
        f"file cresceu: god.py {sb.FILE_LIMIT + 10} -> {sb.FILE_LIMIT + 50} (+40)"
    ]
    bigger = {"files": {"god.py": sb.FILE_LIMIT + 99}, "functions": {"fn.py::big": 500}}
    slack = sb.problems(current, bigger)  # folga acima da tolerância falha
    assert len(slack) == 2 and all("baseline folgada" in m for m in slack)


def test_methods_and_nested_functions_are_qualified(tmp_path: Path) -> None:
    body = "\n".join(f"        a{i} = {i}" for i in range(sb.FUNC_LIMIT + 1))
    (tmp_path / "m.py").write_text(f"class K:\n    def run(self):\n{body}\n", encoding="utf-8")
    assert list(sb.measure(tmp_path, ["m.py"])["functions"]) == ["m.py::K.run"]


def test_baseline_round_trip(tmp_path: Path) -> None:
    data = {"files": {"a.py": 1200}, "functions": {"a.py::f": 150}}
    path = tmp_path / "b.json"
    sb.write_baseline(data, path)
    assert sb.load_baseline(path) == data


def test_slack_baseline_fails_beyond_tolerance() -> None:
    current = {"files": {"a.py": 1100}, "functions": {"a.py::f": 120}}
    ok = {
        "files": {"a.py": 1100 + sb.SLACK_FILE},
        "functions": {"a.py::f": 120 + sb.SLACK_FUNC},
    }
    assert sb.problems(current, ok) == []
    loose = {
        "files": {"a.py": 1100 + sb.SLACK_FILE + 1},
        "functions": {"a.py::f": 120 + sb.SLACK_FUNC + 1},
    }
    found = sb.problems(current, loose)
    assert len(found) == 2
    assert all("baseline folgada" in m and "--tighten" in m for m in found)


def test_orphan_baseline_entries_fail() -> None:
    baseline = {"files": {"gone.py": 1200}, "functions": {"gone.py::f": 150}}
    found = sb.problems({"files": {}, "functions": {}}, baseline)
    assert len(found) == 2 and all("entrada órfã" in m for m in found)


def test_tightened_only_lowers_and_drops_orphans() -> None:
    current = {
        "files": {"a.py": 1100, "grown.py": 1500, "new.py": 1300},
        "functions": {"a.py::f": 120},
    }
    baseline = {
        "files": {"a.py": 1200, "grown.py": 1400, "gone.py": 1100},
        "functions": {"a.py::f": 130, "gone.py::g": 101},
    }
    out = sb.tightened(current, baseline)
    assert out == {
        "files": {"a.py": 1100, "grown.py": 1400},
        "functions": {"a.py::f": 120},
    }
    assert sb.tightened(current, out) == out


def test_run_tighten_refuses_growth_and_writes_otherwise(tmp_path: Path) -> None:
    path = tmp_path / "b.json"
    sb.write_baseline({"files": {"a.py": 1200}, "functions": {}}, path)
    before = path.read_text(encoding="utf-8")
    grown = {"files": {"a.py": 1300}, "functions": {}}
    assert sb.run_tighten(grown, path) == 1
    assert path.read_text(encoding="utf-8") == before
    shrunk = {"files": {"a.py": 1100}, "functions": {}}
    assert sb.run_tighten(shrunk, path) == 0
    assert sb.load_baseline(path) == shrunk
    assert sb.run_tighten(shrunk, path) == 0  # idempotente
