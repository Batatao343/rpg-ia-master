"""Classify a Git change set for deterministic, backend, frontend and protected gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.core.governance import load_protected_paths, protected_changes

ZERO_SHA = "0" * 40
AI_PREFIXES = ("agents/", "evals/", "playtest/")
AI_FILES = {"rag.py", "llm_setup.py", "state.py", "persistence.py"}
AI_SERVICE_PREFIXES = (
    "services/context_",
    "services/memory_",
    "services/narrative_",
    "services/npc_",
    "services/rule_",
    "services/event_",
    "services/actor_",
    "services/conflict_",
)
FRONTEND_PREFIXES = ("web/",)
FRONTEND_FILES = {"api.py", "services/presentation_history.py", "services/auth_sessions.py"}


def _normalized(paths: list[str]) -> list[str]:
    return sorted({PurePosixPath(path.replace("\\", "/")).as_posix().lstrip("./") for path in paths})


def classify(paths: list[str], protected_file: Path) -> dict[str, object]:
    changed = _normalized(paths)
    protected = protected_changes(changed, load_protected_paths(protected_file))
    backend = [
        path for path in changed
        if path in AI_FILES or path.startswith(AI_PREFIXES) or path.startswith(AI_SERVICE_PREFIXES)
    ]
    frontend = [
        path for path in changed
        if path in FRONTEND_FILES or path.startswith(FRONTEND_PREFIXES)
    ]
    return {
        "changed_files": changed,
        "backend_files": backend,
        "frontend_files": frontend,
        "protected_files": protected,
        "backend": bool(backend),
        "frontend": bool(frontend),
        "protected": bool(protected),
        "long_run": False,
    }


def git_changed(root: Path, base: str, head: str) -> list[str]:
    if not head:
        raise ValueError("head SHA is required")
    if not base or base == ZERO_SHA:
        command = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", head]
    else:
        command = ["git", "diff", "--name-only", f"{base}...{head}"]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git change detection failed")
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = args.changed_file or git_changed(root, args.base, args.head)
    result = classify(paths, root / "evals/protected-paths.txt")
    payload = {
        "schema_version": 1,
        "base_sha": args.base,
        "head_sha": args.head,
        **result,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(encoded, encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            for name in ("backend", "frontend", "protected", "long_run"):
                output.write(f"{name}={str(payload[name]).lower()}\n")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
