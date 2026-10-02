"""Regression gates for SPEC-163's deterministic historical migration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
import pytest

from scripts import normalize_specs as normalizer


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.strip()


def _write(path: Path, content: str, *, crlf: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ending = "\r\n" if crlf else "\n"
    path.write_bytes(content.replace("\n", ending).encode("utf-8"))


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "spec-fixture"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "SPEC test")
    _git(repo, "config", "user.email", "spec-test@example.invalid")
    return repo


def _apply(repo: Path, count: int) -> list[normalizer.SpecRecord]:
    records, source_sha, shallow = normalizer.build_plan(repo, expected_count=count)
    normalizer._apply(repo, records, source_sha, shallow, repo / "docs" / "specs-migration-report.md")
    return records


def test_migration_tie_done_evidence_relative_references_and_idempotence(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(
        repo / "specs" / "alpha.md",
        "# alpha\n\n> **Status:** `done`\n> **Depende de:** `beta` e fase externa\n\n[beta](beta.md)\n",
        crlf=True,
    )
    _write(repo / "specs" / "beta.md", "# beta\n\n> **Status:** `draft`\n> **Depende de:** —\n")
    _write(repo / "specs" / "npcs-3-camadas-traits.md", "# traits\n\n> **Status:** `done`\n")
    _write(repo / "specs" / "TEMPLATE.md", "# template\n")
    first_commit = _commit(repo, "create historical specs")
    _write(repo / "docs" / "nested" / "links.md", "[beta](../../specs/beta.md)\n[traits](../../specs/npcs-3-camadas.md)\n")
    _write(repo / "specs" / "beta.md", "# beta\n\n> **Status:** `done`\n> **Depende de:** —\n")
    done_commit = _commit(repo, "complete beta")

    dry_run = subprocess.run(
        [sys.executable, str(Path(normalizer.__file__)), "--dry-run", "--repo", str(repo), "--expected-count", "3"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "SPEC-001" in dry_run.stdout
    assert (repo / "specs" / "alpha.md").exists()

    records = _apply(repo, 3)
    by_slug = {record.slug: record for record in records}
    assert [record.slug for record in records[:3]] == ["alpha", "beta", "npcs-3-camadas-traits"]
    assert all(record.created_commit == first_commit for record in records[:3])
    assert all(record.tie_breaker == "slug_lexical" for record in records[:3])
    assert by_slug["beta"].completed_commit == done_commit
    assert by_slug["beta"].completed_order == 3
    assert by_slug["alpha"].depends_on == ["SPEC-002"]
    assert by_slug["alpha"].depends_on_raw == ["`beta` e fase externa"]
    assert by_slug["alpha"].depends_on_unresolved == ["`beta` e fase externa"]

    alpha = repo / "specs" / "SPEC-001-alpha.md"
    assert b"\r\n" in alpha.read_bytes()
    assert "SPEC-002-beta.md" in alpha.read_text(encoding="utf-8")
    links = (repo / "docs" / "nested" / "links.md").read_text(encoding="utf-8")
    assert "../../specs/SPEC-002-beta.md" in links
    assert "../../specs/SPEC-003-npcs-3-camadas-traits.md" in links

    check = subprocess.run(
        [sys.executable, str(Path(normalizer.__file__)), "--check", "--repo", str(repo), "--expected-count", "3"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr
    assert "passed" in check.stdout
    index = yaml.safe_load((repo / "specs" / "index.yaml").read_text(encoding="utf-8"))
    assert index["source_sha"] == done_commit
    assert [entry["id"] for entry in index["specs"]] == ["SPEC-001", "SPEC-002", "SPEC-003"]

    records_again = _apply(repo, 3)
    assert normalizer._check(repo, records_again, done_commit, False, repo / "docs" / "specs-migration-report.md") == []


def test_followed_rename_uses_original_creation_and_first_done_blob(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shared = "\n".join(["This provenance text survives the rename."] * 8)
    _write(repo / "specs" / "old-title.md", f"# old\n\n> **Status:** `draft`\n\n{shared}\n")
    old_commit = _commit(repo, "draft under old name")
    _git(repo, "mv", "specs/old-title.md", "specs/new-title.md")
    _write(repo / "specs" / "new-title.md", f"# new\n\n> **Status:** `done`\n\n{shared}\n")
    done_commit = _commit(repo, "rename and complete")

    records, _, _ = normalizer.build_plan(repo, expected_count=1)
    record = records[0]
    assert record.slug == "new-title"
    assert record.created_commit == old_commit
    assert record.completed_commit == done_commit


def test_check_reports_broken_internal_markdown_link(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo / "specs" / "only.md", "# only\n\n> **Status:** `done`\n")
    _commit(repo, "create spec")
    _apply(repo, 1)
    _write(repo / "docs" / "broken.md", "[missing](missing.md)\n")

    records, source_sha, shallow = normalizer.build_plan(repo, expected_count=1)
    errors = normalizer._check(repo, records, source_sha, shallow, repo / "docs" / "specs-migration-report.md")
    assert any("broken Markdown link" in error for error in errors)


def test_committed_migration_rechecks_git_anchor_and_rejects_tampered_provenance(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _write(repo / "specs" / "only.md", "# only\n\n> **Status:** `done`\n")
    anchor = _commit(repo, "create historical spec")
    _apply(repo, 1)
    _commit(repo, "commit canonical migration")

    records, source_sha, _ = normalizer.build_plan(repo, expected_count=1)
    assert source_sha == anchor
    assert records[0].created_commit == anchor

    index_path = repo / "specs" / "index.yaml"
    _write(index_path, _read(index_path).replace(f"created_commit: {anchor}", f"created_commit: {'0' * 40}"))
    with pytest.raises(normalizer.MigrationError, match="provenance was altered"):
        normalizer.build_plan(repo, expected_count=1)


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")
