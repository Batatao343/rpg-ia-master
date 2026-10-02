"""Adversarial filesystem/history contracts for the one-time spec migration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "normalize_specs.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "specs").mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Spec fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "specs/alpha.md").write_bytes(
        b"# Alpha\r\n\r\n> **Status:** `done`\r\n> **Depende de:** nenhuma\r\n"
    )
    (repo / "specs/beta.md").write_bytes(
        b"# Beta\r\n\r\n> **Status:** `draft`\r\n"
        b"> **Depende de:** [alpha](./alpha.md)\r\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "historical specs")
    return repo


def _migrate(repo: Path, action: str) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--expected-count", "2", action],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_migration_preserves_private_untracked_data_and_spec_line_endings(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    original = (repo / "specs/alpha.md").read_bytes()
    private_paths = [
        ".claude/settings.local.json", "saves/session.json",
        "data/codex/private.md", "lore_nova/private.txt",
    ]
    for name in private_paths:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"private reference: specs/alpha.md\r\n")
    _migrate(repo, "--apply")
    _migrate(repo, "--check")
    assert (repo / "specs/SPEC-001-alpha.md").read_bytes() == original
    assert (repo / "specs/SPEC-002-beta.md").read_bytes().endswith(
        b"> **Depende de:** [alpha](./SPEC-001-alpha.md)\r\n"
    )
    for name in private_paths:
        assert (repo / name).read_bytes() == b"private reference: specs/alpha.md\r\n"


def test_unrelated_links_do_not_become_dependencies(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    with (repo / "specs/alpha.md").open("ab") as stream:
        stream.write(b"\r\n> **Desbloqueia:** [beta](beta.md)\r\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "document successor")
    _migrate(repo, "--apply")
    index = yaml.safe_load((repo / "specs/index.yaml").read_text(encoding="utf-8"))
    records = {row["slug"]: row for row in index["specs"]}
    assert records["alpha"]["depends_on"] == []
    assert records["beta"]["depends_on"] == ["SPEC-001"]


def test_migration_anchor_and_ids_survive_later_commits(tmp_path: Path) -> None:
    repo = _repository(tmp_path)
    _migrate(repo, "--apply")
    original_index = (repo / "specs/index.yaml").read_bytes()
    original_report = (repo / "docs/specs-migration-report.md").read_bytes()
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "normalize specs")
    (repo / "README.md").write_text("Unrelated documentation\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "unrelated change")
    _migrate(repo, "--check")
    _migrate(repo, "--apply")
    assert (repo / "specs/index.yaml").read_bytes() == original_index
    assert (repo / "docs/specs-migration-report.md").read_bytes() == original_report
