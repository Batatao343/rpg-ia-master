"""Deterministic gameplay-gate oracle contracts (SPEC-212 Etapa 0)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from evals.core.governance import load_cases, load_metrics_registry
from evals.core.runner import run_eval
from evals.evaluators.gameplay_gate import (
    OPERATIONS,
    latency_baseline,
    scan_trace,
    trace_problems,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/gameplay_gate.jsonl"
METRICS = (
    "gameplay_oracle_accuracy",
    "gameplay_oracle_missed_defects",
    "gameplay_oracle_false_alarms",
)


def test_corpus_covers_every_oracle_with_good_and_bad_cases() -> None:
    cases = load_cases(ROOT / "evals" / DATASET)

    assert {case.oracle for case in cases} == {"gameplay_gate"}
    assert {case.suite for case in cases} == {"gameplay_gate"}
    assert {case.input["operation"] for case in cases} == set(OPERATIONS)
    for operation in OPERATIONS:
        group = [case for case in cases if case.input["operation"] == operation]
        assert any(not case.expected["problem_classes"] for case in group), operation
        assert any(case.expected["problem_classes"] for case in group), operation
    assert all(case.description and case.created_from for case in cases)


def test_corpus_passes_with_zero_missed_defects() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="gameplay-gate")

    assert result.passed is True
    assert result.error_case_ids == []
    assert result.metric_values == {
        "gameplay_oracle_accuracy": 1.0,
        "gameplay_oracle_missed_defects": 0.0,
        "gameplay_oracle_false_alarms": 0.0,
    }
    assert result.metadata.provider is None and result.metadata.model is None


def test_metrics_are_registered_as_blocking_hard_gates() -> None:
    registry = load_metrics_registry(ROOT / "evals" / "metrics-registry.yaml")
    for name in METRICS:
        assert registry.metrics[name].kind == "deterministic"
        assert registry.metrics[name].blocking is True
    assert registry.metrics["gameplay_oracle_accuracy"].hard_limit == 1.0
    assert registry.metrics["gameplay_oracle_missed_defects"].hard_limit == 0.0
    assert registry.metrics["gameplay_oracle_false_alarms"].hard_limit == 0.0


def test_a_blind_oracle_is_caught_by_the_dataset(monkeypatch) -> None:
    import evals.evaluators.gameplay_gate as gate

    monkeypatch.setattr(gate, "trace_problems", lambda _operation, _data: [])
    result = run_eval(ROOT, datasets=[DATASET], run_id="blind-oracle")

    assert result.passed is False
    assert result.metric_values["gameplay_oracle_missed_defects"] > 0
    assert any("gameplay_oracle_missed_defects" in item for item in result.hard_failures)


def test_a_paranoid_oracle_is_caught_by_the_dataset(monkeypatch) -> None:
    import evals.evaluators.gameplay_gate as gate

    monkeypatch.setattr(gate, "trace_problems", lambda _operation, _data: ["console:pageerror"])
    result = run_eval(ROOT, datasets=[DATASET], run_id="paranoid-oracle")

    assert result.passed is False
    assert result.metric_values["gameplay_oracle_false_alarms"] > 0


def test_stream_turn_requires_closed_server_ttfmc_but_post_may_be_null() -> None:
    server = {
        "transport": "stream", "pseudo_streaming": True, "ack_server_ms": 5,
        "ttfmc_server_ms": None, "ttlt_server_ms": None,
        "phase_ms": {"router": 1, "context": 1, "narrator": 1, "archivist": 1, "persistence": 1},
    }
    client = {"ack_ms": 1, "first_phase_ms": 2, "ttfmc_ms": 3, "ttlt_ms": 4, "state_ms": 5}
    stream = {"turns": [{"action_id": "a", "transport": "stream", "client": client, "server": server}]}
    post = {"turns": [{
        "action_id": "b", "transport": "post", "client": {k: 9 for k in ("ack_ms", "ttfmc_ms", "ttlt_ms", "state_ms")},
        "server": {**server, "transport": "post", "ack_server_ms": None},
    }]}

    assert trace_problems("latency", stream) == ["latency:null_server_stream"]
    assert trace_problems("latency", post) == []


def test_latency_baseline_is_nearest_rank_and_indicative_below_twenty_turns() -> None:
    turns = [{"client": {"ttfmc_ms": v, "ttlt_ms": v * 2}} for v in (10, 20, 30, 40)]
    baseline = latency_baseline(turns)

    assert baseline["indicative"] is True and baseline["baseline_only"] is True
    assert baseline["ttfmc_ms"] == {"p50": 20, "p95": 40}
    assert baseline["ttlt_ms"] == {"p50": 40, "p95": 80}


def test_scan_cli_exits_nonzero_on_a_duplicated_turn() -> None:
    clean = {"turns": {"turns": [{"action_id": "a", "accepted": True, "receipt_id": "r", "world_turn_after": 1,
                                  "xp_after": 0}], "world_turn_delta": 1, "history_player_delta": 1}}
    dirty = {"turns": {**clean["turns"], "world_turn_delta": 2}}

    def run(trace: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "evals.gameplay_scan"], cwd=ROOT, input=json.dumps(trace),
            capture_output=True, text=True, check=False,
        )

    ok = run(clean)
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["ok"] is True
    bad = run(dirty)
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["problems"] == {"turns": ["duplicate:turn_count_mismatch"]}
    assert scan_trace(dirty)["ok"] is False
