from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from scripts import project_index_ab_harness as harness


def test_path_allowlist_blocks_benchmark_docs_and_index() -> None:
    assert harness._relative("services/memory_provenance.py") == "services/memory_provenance.py"
    assert harness._relative("services/") == "services"
    assert harness._relative("web/src/") == "web/src"
    for path in ("docs/project-index-benchmark/v2/attestation.json", "project_index/query.py", "../AGENTS.md"):
        with pytest.raises(harness.HarnessError):
            harness._relative(path)


def test_condition_b_requires_index_before_source_read(tmp_path: Path, monkeypatch) -> None:
    session_root = tmp_path / "sessions"
    monkeypatch.setattr(harness, "SESSION_ROOT", session_root)
    session_root.mkdir()
    payload = {
        "session_id": "b1-v6", "condition": "B", "status": "running",
        "active_task": "B01", "task_started_at": harness._now(),
        "task_usage": {"B01": {"discovery_calls": 0, "source_bytes_read": 0, "trace": []}},
    }
    harness._save_session(payload)
    args = Namespace(session="b1-v6", task="B01", path="state.py", start=1, lines=1)
    with pytest.raises(harness.HarnessError, match="must query the index"):
        harness.read_source(args)


def test_record_derives_counts_and_enforces_budgets(tmp_path: Path, monkeypatch) -> None:
    session_root = tmp_path / "sessions"
    monkeypatch.setattr(harness, "SESSION_ROOT", session_root)
    session_root.mkdir()
    payload = {
        "session_id": "a1-v6", "task_usage": {
            "B01": {"discovery_calls": 0, "source_bytes_read": 0, "trace": []}
        },
    }
    harness._record(payload, task="B01", op="read", detail={"path": "state.py"}, source_bytes=12)
    usage = payload["task_usage"]["B01"]
    assert usage["discovery_calls"] == 1
    assert usage["source_bytes_read"] == 12
    assert usage["trace"][0]["source_bytes"] == 12


def test_a_cannot_call_index(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(harness, "SESSION_ROOT", tmp_path)
    harness._save_session({
        "session_id": "a1-v6", "condition": "A", "status": "running",
        "active_task": "B01", "task_started_at": harness._now(),
        "task_usage": {"B01": {"discovery_calls": 0, "source_bytes_read": 0, "trace": []}},
    })
    args = Namespace(session="a1-v6", task="B01", mode="query", value="death", limit=5)
    with pytest.raises(harness.HarnessError, match="cannot use Project Index"):
        harness.index_query(args)
