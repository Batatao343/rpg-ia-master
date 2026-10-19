"""Workspace C6: classify a push/PR as docs-only so CI can skip the heavy suite.

docs-only = every changed path is under docs/, handoffs/ or proximas-specs/, or is a
top-level *.md (ESTADO_ATUAL, ROADMAP, CHANGELOG, AGENTS, CLAUDE...). Anything else,
an unknown base (new branch, force push, schedule) or a git error => NOT docs-only
(fail-safe: the full suite runs).

`--doc-tests` prints the test files that read documentation, so the docs-only job
still runs them (59 of ~366 files in 2026-10). Stdlib only: runs before `uv sync`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ZERO_SHA = "0" * 40
DOC_DIRS = ("docs/", "handoffs/", "proximas-specs/")
DOC_TEST_PATTERN = re.compile(r"\.md\b|docs/|handoffs|proximas-specs|\"docs\"")


def is_doc_path(path: str) -> bool:
    posix = PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./")
    if posix.startswith(DOC_DIRS):
        return True
    return "/" not in posix and posix.endswith(".md")


def docs_only(paths: list[str]) -> bool:
    return bool(paths) and all(is_doc_path(path) for path in paths)


def changed_paths(root: Path, base: str, head: str) -> list[str] | None:
    """None = unknown change set (caller must run everything)."""
    if not base or not head or base == ZERO_SHA:
        return None
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        cwd=root, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        return None
    return [line for line in result.stdout.splitlines() if line.strip()]


def doc_tests(root: Path) -> list[str]:
    return sorted(
        path.relative_to(root).as_posix()
        for path in (root / "tests").glob("test_*.py")
        if DOC_TEST_PATTERN.search(path.read_text(encoding="utf-8", errors="replace"))
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--doc-tests", action="store_true")
    args = parser.parse_args(argv)
    if args.doc_tests:
        print(" ".join(doc_tests(args.root)))
        return 0
    paths = changed_paths(args.root, args.base, args.head)
    verdict = paths is not None and docs_only(paths)
    print(f"docs_only={'true' if verdict else 'false'} ({'unknown' if paths is None else len(paths)} files)")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"docs_only={'true' if verdict else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
