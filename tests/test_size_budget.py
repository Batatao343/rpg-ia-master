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
            "Extraia o código novo para módulo próprio; exceção = size_budget.py --update + motivo no commit.",
        ]
    )


def _py(lines: int, func_lines: int) -> str:
    body = "\n".join(f"    x{i} = {i}" for i in range(func_lines - 1))
    filler = "\n".join(f"y{i} = {i}" for i in range(max(0, lines - func_lines)))
    return f"def big():\n{body}\n{filler}\n"


def test_growth_and_new_offenders_fail_shrink_passes(tmp_path: Path) -> None:
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
    assert sb.problems(current, bigger) == []  # encolher é livre


def test_methods_and_nested_functions_are_qualified(tmp_path: Path) -> None:
    body = "\n".join(f"        a{i} = {i}" for i in range(sb.FUNC_LIMIT + 1))
    (tmp_path / "m.py").write_text(f"class K:\n    def run(self):\n{body}\n", encoding="utf-8")
    assert list(sb.measure(tmp_path, ["m.py"])["functions"]) == ["m.py::K.run"]


def test_baseline_round_trip(tmp_path: Path) -> None:
    data = {"files": {"a.py": 1200}, "functions": {"a.py::f": 150}}
    path = tmp_path / "b.json"
    sb.write_baseline(data, path)
    assert sb.load_baseline(path) == data
