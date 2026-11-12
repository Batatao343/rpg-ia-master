"""SPEC-415 R18-R19: reproduz o vermelho->verde dos testes novos de uma spec.

    red_green.sh NNN [--allow-green <nodeid>]... [--equivalence]

Roda os arquivos de teste novos/alterados da branch contra o produto da `main` (worktree
descartavel) e contra a branch; classifica cada teste NOVO. Saida: tabela markdown e a
linha `red_green: K/N OK`; rc 0 so se todos OK.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.dev import land_check as lc
except ImportError:  # executado como script: scripts/dev e o sys.path[0]
    import land_check as lc  # type: ignore[no-redef]

TIMEOUT_S = 600
Runner = Callable[[list[str], str | None], tuple[int, str]]
_RANK = {"pass": 0, "skip": 1, "fail": 2, "error": 3}


@dataclass(frozen=True)
class Row:
    test: str
    main: str
    branch: str
    verdict: str
    ok: bool


def added_tests(old_src: str | None, new_src: str) -> set[str]:
    """Nomes `test_*` (e `TestX::test_*`) presentes em `new_src` e ausentes em `old_src`."""

    def names(src: str) -> set[str]:
        found: set[str] = set()
        for node in ast.parse(src).body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name.startswith("test_"):
                    found.add(node.name)
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for sub in node.body:
                    if isinstance(
                        sub, ast.FunctionDef | ast.AsyncFunctionDef
                    ) and sub.name.startswith("test_"):
                        found.add(f"{node.name}::{sub.name}")
        return found

    return names(new_src) - (names(old_src) if old_src else set())


def junit_outcomes(xml_text: str) -> dict[str, str]:
    """`arquivo::[Classe::]nome` -> pass|fail|error|skip (parametrizados agregados)."""
    out: dict[str, str] = {}
    for case in ET.fromstring(xml_text).iter("testcase"):
        parts = (case.get("classname") or "").split(".")
        cls = parts.pop() if parts and parts[-1].startswith("Test") else ""
        base = (case.get("name") or "").split("[", 1)[0]
        key = "/".join(parts) + ".py::" + (f"{cls}::" if cls else "") + base
        state = "pass"
        if case.find("error") is not None:
            state = "error"
        elif case.find("failure") is not None:
            state = "fail"
        elif case.find("skipped") is not None:
            state = "skip"
        if _RANK[state] >= _RANK[out.get(key, "pass")]:
            out[key] = state
    return out


def _row(name: str, m: str, b: str, allow_green: set[str]) -> Row:
    red = m != "pass"
    label = "vermelho (import)" if m == "error" else ("vermelho" if red else "verde")
    if b != "pass":
        return Row(name, label, b, "FAIL: nao passa na branch", False)
    if red:
        return Row(name, label, "verde", "OK", True)
    if name in allow_green:
        return Row(name, label, "verde", "OK (allow-green)", True)
    return Row(name, label, "verde", "FAIL: nao prova a mudanca", False)


def classify(
    added: set[str],
    main_res: dict[str, str],
    branch_res: dict[str, str],
    allow_green: set[str],
    equivalence: bool,
) -> list[Row]:
    if equivalence:
        rows = []
        for name in sorted(set(main_res) | set(branch_res) | added):
            m, b = main_res.get(name, "error"), branch_res.get(name, "error")
            ok = m == "pass" and b == "pass"
            rows.append(
                Row(name, m, b, "OK" if ok else "FAIL: oraculo exige verde nos dois lados", ok)
            )
        return rows
    if not added:
        msg = "FAIL: spec sem teste novo (declare --equivalence ou peca teste ao executor)"
        return [Row("(nenhum teste novo)", "-", "-", msg, False)]
    return [
        _row(n, main_res.get(n, "error"), branch_res.get(n, "error"), allow_green)
        for n in sorted(added)
    ]


def render(rows: list[Row]) -> str:
    lines = ["| teste | main | branch | veredito |", "|---|---|---|---|"]
    lines += [f"| {r.test} | {r.main} | {r.branch} | {r.verdict} |" for r in rows]
    lines.append(f"red_green: {sum(r.ok for r in rows)}/{len(rows)} OK")
    return "\n".join(lines)


def default_run(args: list[str], cwd: str | None = None) -> tuple[int, str]:
    try:
        out = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_S,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return 124, f"timeout de {TIMEOUT_S}s"
    return out.returncode, out.stdout + out.stderr


def _parse(argv: list[str]) -> tuple[str, set[str], bool] | None:
    if not argv or len(argv[0]) != 3 or not argv[0].isdigit():
        return None
    allow: set[str] = set()
    equivalence = False
    rest = argv[1:]
    while rest:
        head = rest.pop(0)
        if head == "--equivalence":
            equivalence = True
        elif head == "--allow-green" and rest:
            allow.add(rest.pop(0))
        else:
            return None
    return argv[0], allow, equivalence


def _git_show(run: Runner, cwd: str, ref: str, path: str) -> str | None:
    rc, out = run(["git", "show", f"{ref}:{path}"], cwd)
    return out if rc == 0 else None


def _pytest(run: Runner, cwd: str, files: list[str], xml: Path) -> dict[str, str]:
    cmd = ["bash", "scripts/dev/py.sh", "-m", "pytest", *files, "-p", "no:cacheprovider"]
    cmd += ["-n", "2", f"--junitxml={xml.as_posix()}", "-q"]
    run(cmd, cwd)
    return junit_outcomes(xml.read_text(encoding="utf-8")) if xml.exists() else {}


def _collect(run: Runner, wt: str, branch: str) -> tuple[list[str], set[str]] | str:
    rc, out = run(["git", "diff", "--name-only", "--diff-filter=AM", "-z", f"main...{branch}", "--", "tests/"], wt)  # fmt: skip
    if rc != 0:
        return f"git diff falhou: {out.strip()[:120]}"
    changed = [p for p in out.split("\0") if p]
    added: set[str] = set()
    for path in (p for p in changed if Path(p).name.startswith("test_") and p.endswith(".py")):
        new = _git_show(run, wt, branch, path) or ""
        old = _git_show(run, wt, "main", path)
        added |= {f"{path}::{n}" for n in added_tests(old, new)}
    return changed, added


def main(argv: list[str] | None = None, run: Runner | None = None) -> int:
    parsed = _parse(sys.argv[1:] if argv is None else argv)
    if parsed is None:
        print("uso: red_green.sh NNN [--allow-green <nodeid>]... [--equivalence]", file=sys.stderr)
        return 2
    nnn, allow, equivalence = parsed
    run = run or default_run
    branch = f"spec-{nnn}"
    rc, text = run(["git", "worktree", "list", "--porcelain"], None)
    wts = lc.worktrees(text) if rc == 0 else []
    wt = next((p for p, b in wts if b == branch), None)
    if wt is None:
        print(f"{branch}: worktree inexistente", file=sys.stderr)
        return 2
    got = _collect(run, wt, branch)
    if isinstance(got, str):
        print(got, file=sys.stderr)
        return 2
    changed, added = got
    pyfiles = [p for p in changed if Path(p).name.startswith("test_") and p.endswith(".py")]
    if not pyfiles:
        print("red_green: nenhum arquivo test_*.py novo/alterado na branch")
        return 1
    rows = _run_both(run, wt, branch, nnn, changed, pyfiles, added, allow, equivalence)
    print(render(rows))
    return 0 if all(r.ok for r in rows) else 1


def _run_both(
    run: Runner,
    wt: str,
    branch: str,
    nnn: str,
    changed: list[str],
    pyfiles: list[str],
    added: set[str],
    allow: set[str],
    equivalence: bool,
) -> list[Row]:
    tmp = str(Path(wt).parent / f"rpg-redgreen-{nnn}")
    scratch = Path(tempfile.mkdtemp(prefix="rpg-redgreen-"))
    main_wt = lc.worktrees(run(["git", "worktree", "list", "--porcelain"], None)[1])[0][0]
    try:
        run(["git", "worktree", "add", "--detach", tmp, "main"], main_wt)
        run(["git", "checkout", branch, "--", *changed], tmp)
        main_res = _pytest(run, tmp, pyfiles, scratch / "main.xml")
        branch_res = _pytest(run, wt, pyfiles, scratch / "branch.xml")
    finally:
        run(["git", "worktree", "remove", "--force", tmp], main_wt)
        shutil.rmtree(scratch, ignore_errors=True)
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    return classify(added, main_res, branch_res, allow, equivalence)


if __name__ == "__main__":
    sys.exit(main())
