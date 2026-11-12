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
_ASSERT_NAME_RE = re.compile(r"^(?:assert|(?:check|expect|verify)(?:_|$))")
_RAISES_CALLS = frozenset(
    {"pytest.raises", "pytest.warns", "pytest.deprecated_call", "pytest.fail"}
)
_MARK_KINDS = {"skip", "skipif", "xfail"}
_UNITTEST_KINDS = {
    "skip": "skip",
    "skipIf": "skipif",
    "skipUnless": "skipif",
    "expectedFailure": "xfail",
}
_CALL_KINDS = {"skip", "xfail", "importorskip"}
_TEST_FILE_RE = re.compile(r"^tests/(?:.*/)?(?:test_[^/]*\.py|conftest\.py)$")
_BRANCH_RE = re.compile(r"^spec-(\d{3})")
_MAX_DELTA_LINES = 10
HELP = (
    "uso: weak_tests.py [--base B] [--head H] [--spec NNN] [--worktree] [--repo DIR]\n"
    "justificativa na spec: uma linha com o nome do teste (palavra inteira) e a palavra da "
    "própria marca (skip, skipif, xfail, importorskip)."
)

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


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Nome local -> nome canonico, para `pytest`/`unittest` (import as, from-import)."""
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname and a.name in ("pytest", "unittest"):
                    found[a.asname] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module in ("pytest", "unittest"):
            for a in node.names:
                found[a.asname or a.name] = f"{node.module}.{a.name}"
    return found


def _canon(node: ast.AST, aliases: dict[str, str]) -> str:
    name = _dotted(node)
    first, dot, rest = name.partition(".")
    return aliases[first] + dot + rest if first in aliases else name


def _nonempty_str(node: ast.AST | None) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(node.value)


def _reason_and_strict(
    call: ast.Call | None, kind: str, is_call: bool, raw_kind: str = ""
) -> tuple[bool, bool]:
    if call is None:
        return False, False
    kws = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    reason = _nonempty_str(kws.get("reason"))
    if raw_kind in ("skipIf", "skipUnless"):  # unittest: (condicao, motivo)
        reason = reason or (len(call.args) > 1 and _nonempty_str(call.args[1]))
    elif not reason and (kind == "skip" or (is_call and kind == "xfail")) and call.args:
        reason = _nonempty_str(call.args[0])
    strict = isinstance(kws.get("strict"), ast.Constant) and kws["strict"].value is True  # type: ignore[union-attr]
    return bool(reason), strict


class _MarkVisitor(ast.NodeVisitor):
    def __init__(self, tree: ast.Module) -> None:
        self.stack: list[str] = []
        self.found: list[Mark] = []
        self.aliases = _aliases(tree)
        self.mark_vars: dict[str, ast.AST] = {}
        for node in tree.body:  # marca guardada em variavel de modulo, usada como decorador
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if (
                    isinstance(target, ast.Name)
                    and self._mark_from_expr(node.value, "") is not None
                ):
                    self.mark_vars[target.id] = node.value

    @property
    def qual(self) -> str:
        return ".".join(self.stack) or "<module>"

    def _mark_from_expr(self, expr: ast.AST, qual: str) -> Mark | None:
        line = getattr(expr, "lineno", 0)
        if isinstance(expr, ast.Name) and expr.id in self.mark_vars:
            expr = self.mark_vars[expr.id]
        call = expr if isinstance(expr, ast.Call) else None
        head, _, raw = _canon(call.func if call else expr, self.aliases).rpartition(".")
        if head in ("pytest.mark", "mark") and raw in _MARK_KINDS:
            kind = raw
        elif head == "unittest" and raw in _UNITTEST_KINDS:
            kind = _UNITTEST_KINDS[raw]
        else:
            return None
        reason, strict = _reason_and_strict(call, kind, False, raw)
        return Mark(qual, kind, reason, strict, line)

    def _marks_in(self, value: ast.AST | None, qual: str) -> list[Mark]:
        if value is None:
            return []
        items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
        return [m for item in items if (m := self._mark_from_expr(item, qual))]

    def _scoped(self, node: Func | ast.ClassDef) -> None:
        self.stack.append(node.name)
        for deco in node.decorator_list:
            self.found += self._marks_in(deco, self.qual)
            self.visit(deco)
        for child in node.body:
            self.visit(child)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _scoped  # type: ignore[assignment]

    def _pytestmark(self, targets: list[ast.expr], value: ast.AST | None) -> None:
        if any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in targets):
            self.found += self._marks_in(value, self.qual)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._pytestmark(node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._pytestmark([node.target], node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _canon(node.func, self.aliases)
        head, _, kind = name.rpartition(".")
        if head == "pytest" and kind in _CALL_KINDS:
            reason, strict = _reason_and_strict(node, kind, True)
            self.found.append(Mark(self.qual, kind, reason, strict, node.lineno))
        elif name == "pytest.param":
            for kw in node.keywords:
                if kw.arg == "marks":
                    self.found += self._marks_in(kw.value, self.qual)
        self.generic_visit(node)


def marks(src: str) -> list[Mark]:
    tree = ast.parse(src)
    visitor = _MarkVisitor(tree)
    visitor.visit(tree)
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
    """R3: linha da spec com o nome do teste (palavra inteira; arquivo, no `<module>`) e a
    palavra da própria marca (também palavra inteira)."""
    if not spec_text:
        return False
    needle = Path(path).name if mark.qualname == "<module>" else mark.qualname.rsplit(".", 1)[-1]
    name_re = re.compile(rf"(?<![\w.]){re.escape(needle)}(?!\w)")
    kind_re = re.compile(rf"\b{re.escape(mark.kind)}\b")
    return any(name_re.search(line) and kind_re.search(line) for line in spec_text.splitlines())


# Asserções, R5


def _call_base(call: ast.Call) -> str:
    func = call.func
    name = (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )
    return name.lstrip("_")


def _counts_as_assert(node: ast.AST, helpers: set[str], aliases: dict[str, str]) -> bool:
    if isinstance(node, ast.Assert):
        return not (isinstance(node.test, ast.Constant) and bool(node.test.value))
    if isinstance(node, ast.Raise):
        exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        return _dotted(exc) == "AssertionError" if exc else False
    if not isinstance(node, ast.Call):
        return False
    base = _call_base(node)
    return (
        _canon(node.func, aliases) in _RAISES_CALLS
        or _dotted(node.func) == "self.fail"
        or bool(_ASSERT_NAME_RE.match(base))
        or base in helpers
        or base in ASSERT_HELPERS
    )


def assertion_count(
    node: ast.AST, local_helpers: set[str], aliases: dict[str, str] | None = None
) -> int:
    al = aliases or {}
    return sum(_counts_as_assert(sub, local_helpers, al) for sub in ast.walk(node))


def local_assert_helpers(tree: ast.Module) -> set[str]:
    """Funcoes do modulo com asserção propria (um nivel so)."""
    al = _aliases(tree)
    return {
        n.name
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        and not n.name.startswith("test_")
        and assertion_count(n, set(), al) > 0
    }


def _is_fixture(node: Func) -> bool:
    return any(
        _dotted(d.func if isinstance(d, ast.Call) else d).endswith("fixture")
        for d in node.decorator_list
    )


def _is_test_class(node: ast.ClassDef) -> bool:
    return node.name.startswith("Test") or any(_dotted(b).endswith("TestCase") for b in node.bases)


def test_functions(src: str) -> dict[str, Func]:
    """`test_*` de modulo e de classe `Test*`/`TestCase` (qualname `Classe.metodo`), sem fixtures."""
    found: dict[str, Func] = {}
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("test_") and not _is_fixture(node):
                found[node.name] = node
        elif isinstance(node, ast.ClassDef) and _is_test_class(node):
            for sub in node.body:
                is_fn = isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef)
                if is_fn and sub.name.startswith("test_") and not _is_fixture(sub):  # type: ignore[union-attr]
                    found[f"{node.name}.{sub.name}"] = sub  # type: ignore[assignment]
    return found


def weak_new_tests(old_src: str | None, new_src: str) -> list[str]:
    """Qualnames de testes novos (`red_green.added_tests` + classes `TestCase`) sem asserção."""
    tree = ast.parse(new_src)
    helpers, al = local_assert_helpers(tree), _aliases(tree)
    tests = test_functions(new_src)
    fresh = {n.replace("::", ".") for n in added_tests(old_src, new_src)}
    old_names = set(test_functions(old_src)) if old_src else set()
    fresh |= {q for q in tests if not q.startswith("Test") and q not in old_names and "." in q}
    return [
        q for q, node in tests.items() if q in fresh and assertion_count(node, helpers, al) == 0
    ]


def _file_asserts(src: str) -> tuple[int, set[str]]:
    tree = ast.parse(src)
    helpers, al = local_assert_helpers(tree), _aliases(tree)
    tests = test_functions(src)
    return sum(assertion_count(n, helpers, al) for n in tests.values()), set(tests)


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


def _file_findings(
    path: str, old: str | None, new: str | None, spec_text: str | None, nnn: str
) -> tuple[list[Finding], int, int, tuple[int, str, int, int, int] | None]:
    """Achados de um arquivo: (findings, testes novos, marcas novas, delta de asserções)."""
    try:
        if old is not None:
            ast.parse(old)
    except SyntaxError:  # versao antiga ilegivel nao pode virar atalho para esconder pulo
        return [Finding("FAIL", f"weak-tests: {path} versão antiga não parseia")], 0, 0, None
    findings: list[Finding] = []
    n_new = n_mk = 0
    delta = None
    try:
        if new is not None:
            findings += _marks_findings(path, old, new, spec_text, nnn)
            n_mk = len(new_marks(old, new))
            n_new = len(added_tests(old, new))
            findings += [
                Finding(
                    "FAIL", f"weak-tests: {path}::{q} sem assert/pytest.raises/helper de asserção"
                )
                for q in weak_new_tests(old, new)
            ]
        if old is not None:
            before, after, removed = assert_delta(old, new or "")
            if after < before:
                delta = (after - before, path, before, after, removed)
    except SyntaxError:
        findings.append(Finding("INFO", f"weak-tests: {path} não parseia, pulado"))
    return findings, n_new, n_mk, delta


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
        found, n_new, n_mk, delta = _file_findings(path, old, new, spec_text, spec_nnn)
        findings += found
        new_tests += n_new
        n_marks += n_mk
        if delta:
            deltas.append(delta)
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
    args = sys.argv[1:] if argv is None else argv
    if "--help" in args or "-h" in args:
        print(HELP)
        return 0
    opts = _parse(args)
    if opts is None:
        print(HELP, file=sys.stderr)
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
