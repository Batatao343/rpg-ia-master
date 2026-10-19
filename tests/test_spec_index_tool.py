"""scripts/spec_index.py: spec header is the single source of status (workspace #3)."""

from __future__ import annotations

import datetime as dt
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import spec_index

ROOT = Path(__file__).resolve().parents[1]

INDEX = """schema_version: 1
source_sha: abc
history_shallow: false
specs:
- id: SPEC-001
  slug: alpha
  status: draft
  path: specs/SPEC-001-alpha.md
  created_commit: null
  created_at: '2026-01-01'
  completed_commit: null
  completed_at: null
  completed_order: null
  depends_on: []
  depends_on_raw: []
  depends_on_unresolved: []
  tie_breaker: null
  lineage_ambiguous: false
  lineage_note: A very long hand written note that must survive byte for byte even past eighty columns of text
"""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
    ).stdout


def _spec(status: str, title: str) -> str:
    return f"# SPEC — {title}\n\n> **Status:** `{status}`\n"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "r"
    (root / "specs").mkdir(parents=True)
    (root / "specs/index.yaml").write_text(INDEX, encoding="utf-8")
    (root / "specs/SPEC-001-alpha.md").write_text(_spec("draft", "Alpha"), encoding="utf-8")
    (root / "specs/TEMPLATE.md").write_text(
        "# SPEC — <Título>\n\n> **Status:** `draft` | `done`\n> **Criada:** YYYY-MM-DD · **Atualizada:** YYYY-MM-DD\n",
        encoding="utf-8",
    )
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    return root


def test_build_edits_only_status_line_and_appends_new_specs(repo: Path) -> None:
    (repo / "specs/SPEC-001-alpha.md").write_text(_spec("done", "Alpha"), encoding="utf-8")
    (repo / "specs/SPEC-002-beta.md").write_text(
        _spec("draft", "SPEC-002 — Beta"), encoding="utf-8"
    )
    assert spec_index.problems(repo)

    changes = spec_index.build(repo)

    assert changes == ["SPEC-001: draft -> done", "SPEC-002: added (draft)"]
    text = (repo / "specs/index.yaml").read_text(encoding="utf-8")
    assert text.startswith(INDEX.replace("status: draft", "status: done", 1))
    entries = yaml.safe_load(text)["specs"]
    assert [entry["id"] for entry in entries] == ["SPEC-001", "SPEC-002"]
    assert entries[1]["path"] == "specs/SPEC-002-beta.md"
    assert spec_index.problems(repo) == []
    assert spec_index.build(repo) == []


def test_build_refuses_to_drop_indexed_spec(repo: Path) -> None:
    (repo / "specs/SPEC-001-alpha.md").unlink()
    assert spec_index.problems(repo) == ["SPEC-001: in specs/index.yaml but no spec file"]
    with pytest.raises(spec_index.SpecIndexError):
        spec_index.build(repo)


def test_recent_writes_between_markers(repo: Path) -> None:
    estado = repo / "ESTADO_ATUAL.md"
    estado.write_text(
        "top\n<!-- recent:start -->\nold\n<!-- recent:end -->\nbottom\n", encoding="utf-8"
    )
    lines = spec_index.recent(repo, 7)
    assert lines and "SPEC-001 `draft` — Alpha" in lines[0]

    spec_index.write_recent(estado, lines)

    text = estado.read_text(encoding="utf-8")
    assert "old" not in text
    assert text.startswith("top\n<!-- recent:start -->\n- ") and text.endswith(
        "<!-- recent:end -->\nbottom\n"
    )


def test_next_id_sees_reserved_branches_and_creates_from_template(repo: Path) -> None:
    assert spec_index.next_id(repo) == 2
    _git(repo, "branch", "spec-007")
    assert spec_index.next_id(repo) == 8

    path = spec_index.create_spec(repo, 8, "nova-coisa", today=dt.date(2026, 10, 19))

    text = path.read_text(encoding="utf-8")
    assert path.name == "SPEC-008-nova-coisa.md"
    assert text.startswith("# SPEC-008 — nova-coisa\n")
    assert "> **Status:** `draft`\n" in text
    assert "2026-10-19 · **Atualizada:** 2026-10-19" in text
    with pytest.raises(spec_index.SpecIndexError):
        spec_index.create_spec(repo, 8, "nova-coisa")


def test_real_index_matches_spec_headers() -> None:
    """The committed index is generated from headers: any drift fails here and in CI."""

    assert spec_index.problems(ROOT) == []


def test_estado_stays_within_budget() -> None:
    assert (ROOT / "ESTADO_ATUAL.md").stat().st_size <= 8192
