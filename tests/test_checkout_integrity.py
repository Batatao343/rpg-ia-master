"""Cross-platform exact-byte contracts for SPEC-176 clean checkouts."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from evals.core.governance import GovernanceError, validate_repository
from evals.core.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


@pytest.mark.parametrize("autocrlf", ["true", "false"])
def test_checkout_preserves_exact_ruler_and_source_bytes(
    tmp_path: Path, autocrlf: str
) -> None:
    origin = tmp_path / "origin"
    origin.mkdir()
    shutil.copyfile(ROOT / ".gitattributes", origin / ".gitattributes")
    shutil.copytree(ROOT / "evals", origin / "evals", ignore=shutil.ignore_patterns("__pycache__", "runs"))
    # Exercise every extension/name discovered by Project Index, plus binary art.
    samples = [
        "sample.py", "sample.ts", "sample.tsx", "sample.js", "sample.jsx",
        "pyproject.toml", "package.json", "Procfile", ".github/workflows/test.yml",
        ".github/workflows/test.yaml",
    ]
    for relative in samples:
        path = origin / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"first line\nsecond line\n")
    (origin / "sample.webp").write_bytes(b"RIFF\x00\r\n\x00WEBP")
    # Canonical schemas/lock writers may emit CRLF on Windows; force physical
    # LF before capturing the oracle, as required by the committed attributes.
    for path in (origin / "evals").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".json", ".jsonl", ".yaml", ".txt"}:
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    validate_repository(origin / "evals")
    _git(origin, "init")
    _git(origin, "config", "user.name", "Checkout fixture")
    _git(origin, "config", "user.email", "fixture@example.invalid")
    _git(origin, "config", "core.autocrlf", "true")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "exact bytes fixture")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "-c", f"core.autocrlf={autocrlf}", str(origin), str(checkout))

    assert not _git(checkout, "status", "--porcelain")
    validate_repository(checkout / "evals")
    for relative in [*samples, "sample.webp"]:
        assert sha256_file(checkout / relative) == sha256_file(origin / relative)
    assert _git(checkout, "check-attr", "eol", "--", "evals/datasets/regression/narrative_npc.jsonl").strip().endswith(b"eol: lf")


def test_line_ending_tampering_still_fails_closed(tmp_path: Path) -> None:
    eval_root = tmp_path / "evals"
    shutil.copytree(ROOT / "evals", eval_root, ignore=shutil.ignore_patterns("__pycache__", "runs"))
    validate_repository(eval_root)
    dataset = eval_root / "datasets/regression/narrative_npc.jsonl"
    data = dataset.read_bytes()
    assert b"\r\n" not in data
    dataset.write_bytes(data.replace(b"\n", b"\r\n"))

    with pytest.raises(GovernanceError, match="dataset hash mismatch"):
        validate_repository(eval_root)
