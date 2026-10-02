"""Stable SHA-256 identities for public eval datasets and registries."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Hash the exact bytes on disk; line-ending changes intentionally invalidate locks."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def sha256_json(value: object) -> str:
    """Hash a canonical JSON representation for ordered selection/config identities."""

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def case_selection_hash(case_ids: list[str]) -> str:
    """Hash the selected case set independently of execution order."""

    if not case_ids:
        raise ValueError("case selection cannot be empty")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case selection ids must be unique")
    return sha256_json(sorted(case_ids))


def repository_identity(root: Path) -> tuple[str, str, bool]:
    """Return HEAD, exact Git-visible worktree hash and dirty state."""

    root = root.resolve()
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
    if head.returncode:
        raise RuntimeError(f"cannot resolve product SHA: {head.stderr.strip()}")
    visible = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        env=environment,
    )
    if visible.returncode:
        raise RuntimeError("cannot enumerate Git-visible product files")
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        capture_output=True,
        env=environment,
    )
    if status.returncode:
        raise RuntimeError("cannot determine product worktree status")

    digest = hashlib.sha256()
    relative_paths = sorted(
        item.decode("utf-8", errors="replace")
        for item in visible.stdout.split(b"\0")
        if item
    )
    for relative in relative_paths:
        encoded_path = relative.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        path = root / Path(relative)
        if path.is_file():
            data = path.read_bytes()
            digest.update(b"F")
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
        else:
            digest.update(b"MISSING")
    return head.stdout.strip(), f"sha256:{digest.hexdigest()}", bool(status.stdout)
