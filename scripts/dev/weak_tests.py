"""SPEC-417 R1-R8: catraca de teste enfraquecido (skip/xfail novo sem motivo, teste sem assert).

    weak_tests.py [--base main] [--head HEAD] [--spec NNN] [--worktree] [--repo DIR]

Compara `tests/**/test_*.py` e `conftest.py` entre `merge-base(base, head)` e `head` (ou o
disco, com `--worktree`). Deteccao por AST, nunca regex. rc 0 sem `FAIL`, 1 com, 2 uso errado.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Literal, NamedTuple

try:
    from scripts.dev.red_green import added_tests
except ImportError:  # executado como script: scripts/dev e o sys.path[0]
    from red_green import added_tests  # type: ignore[no-redef]

# Helpers que levantam AssertionError sem prefixo de asserção (crescer aparece no diff).
ASSERT_HELPERS = frozenset({"fuzz_operation"})
_ASSERT_PREFIXES = ("assert", "check_", "expect_", "verify_")
_RAISES_CALLS = frozenset({"raises", "warns", "deprecated_call", "fail"})
_MARK_KINDS = {"skip", "skipif", "xfail"}
_CALL_KINDS = {"skip", "xfail", "importorskip"}
_JUSTIFY_WORDS = ("skip", "skipif", "xfail", "importorskip")
_TEST_FILE_RE = re.compile(r"^tests/(?:.*/)?(?:test_[^/]*\.py|conftest\.py)$")
_BRANCH_RE = re.compile(r"^spec-(\d{3})")
_MAX_DELTA_LINES = 10

Func = ast.FunctionDef | ast.AsyncFunctionDef


class Mark(NamedTuple):
    qualname: str
    kind: str
    has_reason: bool
    strict: bool
    lineno: int


class Finding(NamedTuple):
    level: Literal["FAIL", "INFO", "OK"]
    text: str


# Marcas de pulo, R2


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _nonempty_str(node: ast.AST | None) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(node.value)


def _reason_and_strict(call: ast.Call | None, kind: str, is_call: bool) -> tuple[bool, bool]:
    if call is None:
        return False, False
    kws = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    reason = _nonempty_str(kws.get("reason"))
    positional_ok = kind == "skip" or (is_call and kind == "xfail")
    if not reason and positional_ok and call.args:
        reason = _nonempty_str(call.args[0])
    strict = isinstance(kws.get("strict"), ast.Constant) and kws["strict"].value is True  # type: ignore[union-attr]
    return reason, strict


def _mark_from_expr(expr: ast.AST, qual: str) -> Mark | None:
    call = expr if isinstance(expr, ast.Call) else None
    name = _dotted(call.func if call else expr)
    head, _, kind = name.rpartition(".")
    if head not in ("pytest.mark", "mark") or kind not in _MARK_KINDS:
        return None
    reason, strict = _reason_and_strict(call, kind, False)
    return Mark(qual, kind, reason, strict, getattr(expr, "lineno", 0))


def _marks_in(value: ast.AST | None, qual: str) -> list[Mark]:
    if value is None:
        return []
    items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
    return [m for item in items if (m := _mark_from_expr(item, qual))]


class _MarkVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.found: list[Mark] = []

    @property
    def qual(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _scoped(self, node: Func | ast.ClassDef) -> None:
        self.stack.append(node.name)
        for deco in node.decorator_list:
            self.found += _marks_in(deco, self.qual)
            self.visit(deco)
        for child in node.body:
            self.visit(child)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            self.found += _marks_in(node.value, self.qual)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func)
        head, _, kind = name.rpartition(".")
        if head == "pytest" and kind in _CALL_KINDS:
            reason, strict = _reason_and_strict(node, kind, True)
            self.found.append(Mark(self.qual, kind, reason, strict, node.lineno))
        elif name == "pytest.param":
            for kw in node.keywords:
                if kw.arg == "marks":
                    self.found += _marks_in(kw.value, self.qual)
        self.generic_visit(node)


def marks(src: str) -> list[Mark]:
    visitor = _MarkVisitor()
    visitor.visit(ast.parse(src))
    return visitor.found


def new_marks(old_src: str | None, new_src: str) -> list[Mark]:
    """R3: multiconjunto (qualname, kind, has_reason) novo menos antigo."""
    seen = Counter((m.qualname, m.kind, m.has_reason) for m in (marks(old_src) if old_src else []))
    fresh: list[Mark] = []
    for mark in sorted(marks(new_src), key=lambda m: m.lineno):
        key = (mark.qualname, mark.kind, mark.has_reason)
        if seen[key] > 0:
            seen[key] -= 1
        else:
            fresh.append(mark)
    return fresh


def justified(mark: Mark, path: str, spec_text: str | None) -> bool:
    """R3: uma linha da spec com o nome do teste (ou arquivo, no `<module>`) e a palavra da marca."""
    if not spec_text:
        return False
    needle = Path(path).name if mark.qualname == "<module>" else mark.qualname.rsplit(".", 1)[-1]
    return any(
        needle in line and any(w in line for w in _JUSTIFY_WORDS) for line in spec_text.splitlines()
    )


# Asserções, R5


def _call_name(call: ast.Call) -> str:
    func = call.func
    name = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )
    return name.lstrip("_")


def _counts_as_assert(node: ast.AST, local_helpers: set[str]) -> bool:
    if isinstance(node, ast.Assert):
        return not (isinstance(node.test, ast.Constant) and bool(node.test.value))
    if isinstance(node, ast.Raise):
        exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        return _dotted(exc) == "AssertionError" if exc else False
    if not isinstance(node, ast.Call):
        return False
    name = _call_name(node)
    return (
        name in _RAISES_CALLS
        or name.startswith(_ASSERT_PREFIXES)
        or name in local_helpers
        or name in ASSERT_HELPERS
    )


def assertion_count(node: ast.AST, local_helpers: set[str]) -> int:
    return sum(_counts_as_assert(sub, local_helpers) for sub in ast.walk(node))


def local_assert_helpers(tree: ast.Module) -> set[str]:
    """Funcoes do modulo com asserção propria (um nivel so)."""
    return {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        and not n.name.startswith("test_")
        and assertion_count(n, set()) > 0
    }


def _is_fixture(node: Func) -> bool:
    return any(
        _dotted(d.func if isinstance(d, ast.Call) else d).endswith("fixture")
        for d in node.decorator_list
    )


def test_functions(src: str) -> dict[str, Func]:
    """`test_*` de modulo e de classe `Test*` (qualname `Classe.metodo`), sem fixtures."""
    found: dict[str, Func] = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test_") and not _is_fixture(node):
                found[node.name] = node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                is_fn = isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef)
                if is_fn and sub.name.startswith("test_") and not _is_fixture(sub):  # type: ignore[union-attr]
                    found[f"{node.name}.{sub.name}"] = sub  # type: ignore[assignment]
    return found


def weak_new_tests(old_src: str | None, new_src: str) -> list[str]:
    """Qualnames de testes novos (deteccao de `red_green.added_tests`) sem asserção."""
    tree = ast.parse(new_src)
    helpers = local_assert_helpers(tree)
    tests = test_functions(new_src)
    fresh = {n.replace("::", ".") for n in added_tests(old_src, new_src)}
    return [q for q, node in tests.items() if q in fresh and assertion_count(node, helpers) == 0]


def _file_asserts(src: str) -> tuple[int, set[str]]:
    helpers = local_assert_helpers(ast.parse(src))
    tests = test_functions(src)
    return sum(assertion_count(n, helpers) for n in tests.values()), set(tests)


def assert_delta(old_src: str, new_src: str) -> tuple[int, int, int]:
    """(asserções antes, depois, testes removidos) de um arquivo de teste."""
    before, old_names = _file_asserts(old_src)
    after, new_names = _file_asserts(new_src)
    return before, after, len(old_names - new_names)


# git


def _git(repo: Path, *args: str) -> tuple[int, str]:
    out = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return out.returncode, out.stdout


def changed_test_files(
    repo: Path, base: str, head: str, *, worktree: bool = False
) -> list[tuple[str | None, str | None]]:
    """(caminho antigo, caminho novo) dos arquivos de teste tocados; None = criado/apagado."""
    rng = [base] if worktree else [f"{base}...{head}"]
    rc, out = _git(repo, "diff", "--name-status", "-M", "--diff-filter=AMRD", *rng, "--", "tests/")
    if rc != 0:
        raise ValueError(f"git diff falhou para {' '.join(rng)}")
    pairs: list[tuple[str | None, str | None]] = []
    for line in out.splitlines():
        cols = line.split("\t")
        status, paths = cols[0][0], cols[1:]
        old, new = (paths[0], paths[-1])
        pairs.append((None if status == "A" else old, None if status == "D" else new))
    if worktree:
        _, extra = _git(repo, "ls-files", "--others", "--exclude-standard", "--", "tests/")
        pairs += [(None, p) for p in extra.splitlines() if p]
    return [(o, n) for o, n in pairs if _TEST_FILE_RE.match(n or o or "")]


def _read_old(repo: Path, merge_base: str, path: str | None) -> str | None:
    if path is None:
        return None
    rc, out = _git(repo, "show", f"{merge_base}:{path}")
    return out if rc == 0 else None


def _read_new(repo: Path, head: str, path: str | None, worktree: bool) -> str | None:
    if path is None:
        return None
    if worktree:
        file = repo / path
        return file.read_text(encoding="utf-8") if file.exists() else None
    rc, out = _git(repo, "show", f"{head}:{path}")
    return out if rc == 0 else None


# check


def _marks_findings(
    path: str, old: str | None, new: str, spec_text: str | None, nnn: str
) -> list[Finding]:
    out: list[Finding] = []
    for m in new_marks(old, new):
        where = f"{path}::{m.qualname}"
        if not m.has_reason and not justified(m, path, spec_text):
            out.append(
                Finding(
                    "FAIL",
                    f"weak-tests: {where} {m.kind} sem reason (l. {m.lineno}) e sem justificativa"
                    f" na SPEC-{nnn or '???'}",
                )
            )
        if m.kind == "xfail" and not m.strict:
            out.append(
                Finding("INFO", f"weak-tests: xfail novo sem strict=True: {where} (l. {m.lineno})")
            )
    return out


def _delta_findings(deltas: list[tuple[int, str, int, int, int]]) -> list[Finding]:
    deltas.sort()
    shown = deltas[:_MAX_DELTA_LINES]
    out = [
        Finding(
            "INFO", f"weak-tests: assert-delta {p} {b} -> {a} ({d:+d}), {r} teste(s) removido(s)"
        )
        for d, p, b, a, r in shown
    ]
    if len(deltas) > len(shown):
        out.append(Finding("INFO", f"weak-tests: (+{len(deltas) - len(shown)} arquivos)"))
    return out


def check(
    repo: Path,
    base: str,
    head: str,
    spec_text: str | None,
    *,
    worktree: bool = False,
    spec_nnn: str = "",
) -> list[Finding]:
    repo = Path(repo)
    rc, mb = _git(repo, "merge-base", base, head)
    if rc != 0:
        raise ValueError(f"merge-base de {base} e {head} falhou")
    merge_base = mb.strip()
    pairs = changed_test_files(repo, merge_base if worktree else base, head, worktree=worktree)
    findings: list[Finding] = []
    deltas: list[tuple[int, str, int, int, int]] = []
    new_tests = n_marks = 0
    for old_path, new_path in pairs:
        path = new_path or old_path or ""
        old = _read_old(repo, merge_base, old_path)
        new = _read_new(repo, head, new_path, worktree)
        try:
            if new is not None:
                findings += _marks_findings(path, old, new, spec_text, spec_nnn)
                n_marks += len(new_marks(old, new))
                weak = weak_new_tests(old, new)
                new_tests += len(added_tests(old, new))
                findings += [
                    Finding(
                        "FAIL",
                        f"weak-tests: {path}::{q} sem assert/pytest.raises/helper de asserção",
                    )
                    for q in weak
                ]
            if old is not None:
                before, after, removed = assert_delta(old, new or "")
                if after < before:
                    deltas.append((after - before, path, before, after, removed))
        except SyntaxError:
            findings.append(Finding("INFO", f"weak-tests: {path} não parseia, pulado"))
    findings += _delta_findings(deltas)
    if not any(f.level == "FAIL" for f in findings):
        findings.append(
            Finding(
                "OK",
                f"weak-tests: {len(pairs)} arquivos, {new_tests} testes novos, {n_marks} marcas novas",
            )
        )
    return findings


# CLI


def _parse(argv: list[str]) -> dict[str, str | bool] | None:
    opts: dict[str, str | bool] = {
        "base": "main",
        "head": "HEAD",
        "spec": "",
        "repo": ".",
        "worktree": False,
    }
    it = iter(argv)
    for arg in it:
        key = arg.removeprefix("--")
        if arg == "--worktree":
            opts["worktree"] = True
        elif arg.startswith("--") and key in opts:
            value = next(it, None)
            if value is None:
                return None
            opts[key] = value
        else:
            return None
    return opts


def _spec_context(repo: Path, opts: dict[str, str | bool]) -> tuple[str, str | None, list[Finding]]:
    nnn = str(opts["spec"])
    if not nnn:
        _, branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        m = _BRANCH_RE.match(branch.strip())
        nnn = m.group(1) if m else ""
    if not nnn:
        return (
            "",
            None,
            [
                Finding(
                    "INFO",
                    "weak-tests: sem spec (branch fora de spec-NNN): justificativa indisponível",
                )
            ],
        )
    files = sorted((repo / "specs").glob(f"SPEC-{nnn}-*.md"))
    text = files[0].read_text(encoding="utf-8") if files else None
    return nnn, text, []


def main(argv: list[str] | None = None) -> int:
    opts = _parse(sys.argv[1:] if argv is None else argv)
    if opts is None:
        print(
            "uso: weak_tests.py [--base B] [--head H] [--spec NNN] [--worktree] [--repo DIR]",
            file=sys.stderr,
        )
        return 2
    repo = Path(str(opts["repo"])).resolve()
    nnn, spec_text, notes = _spec_context(repo, opts)
    try:
        findings = notes + check(
            repo,
            str(opts["base"]),
            str(opts["head"]),
            spec_text,
            worktree=bool(opts["worktree"]),
            spec_nnn=nnn,
        )
    except ValueError as exc:
        print(f"weak-tests: {exc}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"{f.level} {f.text}")
    return 1 if any(f.level == "FAIL" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
