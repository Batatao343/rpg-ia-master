"""SPEC-415 R18-R19: `scripts/dev/red_green.py` reproduz o vermelho->verde."""

from __future__ import annotations

import contextlib
from pathlib import Path

from scripts.dev import red_green as rg

OLD = "def test_a():\n    pass\n"
NEW = OLD + "def test_b():\n    pass\n\nclass TestX:\n    def test_c(self):\n        pass\n"


def test_added_tests_ast() -> None:
    assert rg.added_tests(OLD, NEW) == {"test_b", "TestX::test_c"}
    assert rg.added_tests(None, NEW) == {"test_a", "test_b", "TestX::test_c"}


def _xml(*cases: tuple[str, str, str]) -> str:
    body = ""
    for cls, name, state in cases:
        child = {"pass": "", "fail": "<failure/>", "error": "<error/>"}[state]
        body += f'<testcase classname="{cls}" name="{name}">{child}</testcase>'
    return f"<testsuites><testsuite>{body}</testsuite></testsuites>"


def test_junit_outcomes_aggregates_params() -> None:
    out = rg.junit_outcomes(
        _xml(
            ("tests.test_m", "test_b[1]", "pass"),
            ("tests.test_m", "test_b[2]", "fail"),
            ("tests.test_m.TestX", "test_c", "pass"),
        )
    )
    assert out == {"tests/test_m.py::test_b": "fail", "tests/test_m.py::TestX::test_c": "pass"}


def test_classify_rules() -> None:
    added = {"a", "b", "c", "d"}
    main = {"a": "fail", "b": "pass", "c": "pass", "d": "error"}
    branch = {"a": "pass", "b": "pass", "c": "fail", "d": "pass"}
    rows = {r.test: r for r in rg.classify(added, main, branch, set(), False)}
    assert rows["a"].ok and not rows["b"].ok and not rows["c"].ok
    assert rows["d"].ok and "import" in rows["d"].main
    allowed = {r.test: r for r in rg.classify({"b"}, main, branch, {"b"}, False)}
    assert allowed["b"].ok
    # ausente na main (modulo novo): conta vermelho
    assert rg.classify({"z"}, {}, {"z": "pass"}, set(), False)[0].ok
    assert not rg.classify(set(), {}, {}, set(), False)[0].ok
    eq = rg.classify(set(), {"a": "pass", "b": "fail"}, {"a": "pass", "b": "pass"}, set(), True)
    assert [r.ok for r in eq] == [True, False]


def test_render_summary_line() -> None:
    rows = rg.classify({"a"}, {"a": "fail"}, {"a": "pass"}, set(), False)
    assert rg.render(rows).splitlines()[-1] == "red_green: 1/1 OK"


def test_temp_worktree_removed_on_error() -> None:
    calls: list[list[str]] = []

    def run(args: list[str], cwd: str | None = None) -> tuple[int, str]:
        calls.append(args)
        if args[:3] == ["git", "worktree", "list"]:
            main = "worktree /m\nbranch refs/heads/main\n\n"
            return 0, main + "worktree /w/rpg-spec-999\nbranch refs/heads/spec-999\n"
        if args[:2] == ["git", "diff"]:
            return 0, "tests/test_x.py\0"
        if args[:2] == ["git", "show"]:
            return 0, "def test_a():\n    pass\n"
        if args[:2] == ["bash", "scripts/dev/py.sh"]:
            raise RuntimeError("pytest explodiu")
        return 0, ""

    with contextlib.suppress(RuntimeError):
        rg.main(["999"], run)
    assert any(c[:3] == ["git", "worktree", "remove"] for c in calls)


def test_bad_usage(tmp_path: Path) -> None:
    assert rg.main(["x"], lambda a, c=None: (0, "")) == 2
    assert rg.main(["999", "--allow-green"], lambda a, c=None: (0, "")) == 2
