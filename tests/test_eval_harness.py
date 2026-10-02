"""End-to-end contracts for the deterministic eval harness (SPEC-167)."""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from evals.__main__ import main
from evals.core.adapters import AdapterCase, AdapterOutput, AdapterRegistry
from evals.core.compare import compare_runs
from evals.core.governance import GovernanceError
from evals.core.hashing import repository_identity
from evals.core.runner import run_eval, write_run
from evals.core.schemas import EVALUATOR_VERSION


ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_DATASET = "datasets/regression/governance.jsonl"
HARNESS_DATASET = "datasets/regression/harness.jsonl"


def test_runner_known_good_is_offline_and_reports_frozen_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in (
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "QWEN_API_KEY",
        "MINIMAX_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)

    random.seed(991)
    expected_next_random = random.random()
    random.seed(991)
    result = run_eval(
        ROOT,
        datasets=[GOVERNANCE_DATASET],
        case_ids={"governance.exact.good"},
        run_id="known-good",
    )
    json_path, markdown_path = write_run(result, tmp_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))

    assert result.passed is True
    assert result.metric_values == {"exact_match": 1.0}
    assert result.metadata.provider is None
    assert result.metadata.product_sha
    assert result.metadata.product_tree_hash.startswith("sha256:")
    assert isinstance(result.metadata.product_dirty, bool)
    assert result.metadata.dataset_hashes
    assert result.metadata.ruler_hashes
    assert payload["metadata"]["evaluator_version"] == EVALUATOR_VERSION
    assert "Product SHA" in markdown_path.read_text(encoding="utf-8")
    assert "RPG_FORCE_MOCK" not in __import__("os").environ
    assert random.random() == expected_next_random


def test_runner_known_bad_is_a_hard_failure_with_diagnostics() -> None:
    result = run_eval(
        ROOT,
        datasets=[GOVERNANCE_DATASET],
        case_ids={"governance.exact.bad"},
        run_id="known-bad",
    )

    assert result.passed is False
    assert result.results[0].passed is False
    assert result.case_diagnostics["governance.exact.bad"]
    assert "case failed: governance.exact.bad" in result.hard_failures
    assert result.metric_values == {"exact_match": 0.0}


def test_cli_returns_nonzero_for_known_bad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evals",
            "--root",
            str(ROOT),
            "run",
            "--dataset",
            GOVERNANCE_DATASET,
            "--case",
            "governance.exact.bad",
            "--run-id",
            "cli-known-bad",
            "--output",
            str(tmp_path),
        ],
    )

    assert main() == 1
    assert (tmp_path / "cli-known-bad.json").is_file()


def test_harness_reuses_playtest_invariants_for_good_and_bad_state() -> None:
    result = run_eval(ROOT, datasets=[HARNESS_DATASET], run_id="invariants")
    by_id = {case.case_id: case for case in result.results}

    assert result.passed is True
    assert by_id["harness.invariants.clean"].actual == []
    assert by_id["harness.invariants.negative-gold"].actual == ["economy.gold_negative"]
    assert any(
        "economy.gold_negative" in item
        for item in result.case_diagnostics["harness.invariants.negative-gold"]
    )


def test_unknown_suite_is_accounted_as_error_not_dropped() -> None:
    result = run_eval(
        ROOT,
        datasets=[HARNESS_DATASET],
        case_ids={"harness.invariants.clean"},
        registry=AdapterRegistry(),
        run_id="missing-adapter",
    )

    assert result.passed is False
    assert result.results == []
    assert result.error_case_ids == ["harness.invariants.clean"]
    assert "no product adapter" in result.case_diagnostics["harness.invariants.clean"][0]


def test_adapter_view_cannot_read_fixture_authored_expected() -> None:
    seen_fields: set[str] = set()

    class AdversarialAdapter:
        adapter_id = "adversarial"

        def execute(self, case: AdapterCase) -> AdapterOutput:
            seen_fields.update(vars(case))
            assert not hasattr(case, "expected")
            assert not hasattr(case, "oracle")
            return AdapterOutput(actual=case.input["actual"])

    result = run_eval(
        ROOT,
        datasets=[GOVERNANCE_DATASET],
        case_ids={"governance.exact.bad"},
        registry=AdapterRegistry({"governance": AdversarialAdapter()}),
        run_id="oracle-isolation",
    )

    assert "expected" not in seen_fields
    assert "oracle" not in seen_fields
    assert result.passed is False


def test_comparison_accepts_compatible_runs_and_rejects_identity_drift(tmp_path: Path) -> None:
    baseline = run_eval(
        ROOT,
        datasets=[HARNESS_DATASET],
        case_ids={"harness.invariants.clean"},
        run_id="baseline",
    )
    current = baseline.model_copy(update={"run_id": "current"})
    baseline_path, _ = write_run(baseline, tmp_path)
    current_path, _ = write_run(current, tmp_path)

    comparison = compare_runs(ROOT, current_path, baseline_path)

    assert comparison["passed"] is True
    assert comparison["deltas"] == {"exact_match": 0.0}

    incompatible = current.model_copy(
        update={"run_id": "incompatible", "metadata": current.metadata.model_copy(update={"seed": 99})}
    )
    incompatible_path, _ = write_run(incompatible, tmp_path)
    with pytest.raises(GovernanceError, match="seed"):
        compare_runs(ROOT, incompatible_path, baseline_path)


def test_run_id_cannot_escape_output_directory() -> None:
    with pytest.raises(ValueError, match="run_id"):
        run_eval(
            ROOT,
            datasets=[HARNESS_DATASET],
            case_ids={"harness.invariants.clean"},
            run_id="../escape",
        )


def test_product_identity_changes_for_dirty_worktree_bytes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source = repo / "product.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    environment = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    for arguments in (
        ("init",),
        ("config", "user.name", "Eval fixture"),
        ("config", "user.email", "eval@example.invalid"),
        ("add", "."),
        ("commit", "-m", "fixture"),
    ):
        subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            env=environment,
        )

    clean_sha, clean_tree, clean_dirty = repository_identity(repo)
    source.write_text("VALUE = 2\n", encoding="utf-8")
    dirty_sha, dirty_tree, dirty = repository_identity(repo)

    assert dirty_sha == clean_sha
    assert dirty_tree != clean_tree
    assert clean_dirty is False
    assert dirty is True
