"""Governance and anti-gaming gates for SPEC-165."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from evals.core.governance import (
    GovernanceError,
    assert_baseline_compatible,
    assert_optimization_paths_allowed,
    load_cases,
    load_metrics_registry,
    validate_repository,
)
from evals.core.hashing import case_selection_hash, sha256_file
from evals.core.schemas import EVALUATOR_VERSION, EvalRunMetadata, EvalRunResult
from evals.evaluators import ExactEvaluator


ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals"


def _copy_evals(tmp_path: Path) -> Path:
    target = tmp_path / "evals"
    shutil.copytree(EVAL_ROOT, target)
    return target


def _metadata(**overrides: object) -> EvalRunMetadata:
    values: dict[str, object] = {
        "schema_version": 1,
        "evaluator_version": "1.0.0",
        "ruler_hashes": {"evaluators/exact.py": f"sha256:{'e' * 64}"},
        "metrics_schema_version": 1,
        "metrics_registry_hash": f"sha256:{'d' * 64}",
        "product_sha": "abcdef123456",
        "product_tree_hash": f"sha256:{'f' * 64}",
        "product_dirty": False,
        "dataset_hashes": {"routing": f"sha256:{'a' * 64}"},
        "case_selection_hash": case_selection_hash(["case.a", "case.b"]),
        "seed": 7,
        "started_at": datetime.now(UTC),
    }
    values.update(overrides)
    return EvalRunMetadata.model_validate(values)


def test_repository_governance_lock_is_valid_and_complete() -> None:
    manifest = validate_repository(EVAL_ROOT)

    dataset = EVAL_ROOT / "datasets/regression/governance.jsonl"
    assert manifest["datasets"]["datasets/regression/governance.jsonl"] == sha256_file(dataset)
    assert manifest["evaluator_version"] == EVALUATOR_VERSION
    assert len(load_cases(dataset)) == 2


def test_dataset_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    dataset = eval_root / "datasets/regression/governance.jsonl"
    dataset.write_text(dataset.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="dataset hash mismatch"):
        validate_repository(eval_root)


def test_evaluator_version_mismatch_fails_closed(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    manifest_path = eval_root / "manifest.lock.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["evaluator_version"] = "999.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(GovernanceError, match="evaluator_version"):
        validate_repository(eval_root)


def test_evaluator_source_change_fails_closed(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    evaluator = eval_root / "evaluators/exact.py"
    evaluator.write_text("raise RuntimeError('tampered evaluator')\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="ruler source hash mismatch"):
        validate_repository(eval_root)


def test_core_ruler_change_fails_closed(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    schemas = eval_root / "core/schemas.py"
    schemas.write_text(schemas.read_text(encoding="utf-8") + "\n# semantic drift\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="ruler source hash mismatch"):
        validate_repository(eval_root)


def test_stale_generated_schema_fails_closed(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    schema_path = eval_root / "eval-case.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["title"] = "tampered"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(GovernanceError, match="stale generated schema"):
        validate_repository(eval_root)


def test_public_holdout_is_rejected(tmp_path: Path) -> None:
    eval_root = _copy_evals(tmp_path)
    (eval_root / "datasets/holdout").mkdir()

    with pytest.raises(GovernanceError, match="holdout"):
        validate_repository(eval_root)


def test_protected_paths_block_optimizer_but_not_product_paths() -> None:
    protected_file = EVAL_ROOT / "protected-paths.txt"

    with pytest.raises(GovernanceError, match="protected eval paths"):
        assert_optimization_paths_allowed(
            ["agents/router.py", "evals/evaluators/exact.py"], protected_file
        )
    assert_optimization_paths_allowed(["agents/router.py", "tests/test_router.py"], protected_file)
    with pytest.raises(GovernanceError, match="protected eval paths"):
        assert_optimization_paths_allowed(
            ["EVALS/EVALUATORS/exact.py", "evals/protected-paths.txt"], protected_file
        )


def test_protection_list_cannot_remove_its_own_controls(tmp_path: Path) -> None:
    protected_file = tmp_path / "protected-paths.txt"
    protected_file.write_text("web/e2e/contracts\n", encoding="utf-8")

    with pytest.raises(GovernanceError, match="removed required controls"):
        assert_optimization_paths_allowed(["agents/router.py"], protected_file)


def test_exact_evaluator_has_known_good_and_known_bad() -> None:
    cases = {case.id: case for case in load_cases(EVAL_ROOT / "datasets/regression/governance.jsonl")}
    evaluator = ExactEvaluator()
    dataset_hash = f"sha256:{'b' * 64}"

    good = cases["governance.exact.good"]
    good_result = evaluator.evaluate(
        good,
        good.input["actual"],
        product_sha="abcdef1",
        dataset_hash=dataset_hash,
        seed=1,
    )
    bad = cases["governance.exact.bad"]
    bad_result = evaluator.evaluate(
        bad,
        bad.input["actual"],
        product_sha="abcdef1",
        dataset_hash=dataset_hash,
        seed=1,
    )

    assert good_result.passed is True
    assert good_result.metric_values == {"exact_match": 1.0}
    assert bad_result.passed is False
    assert bad_result.metric_values == {"exact_match": 0.0}
    assert bad_result.diagnostics


def test_exact_evaluator_distinguishes_json_boolean_from_number() -> None:
    case = load_cases(EVAL_ROOT / "datasets/regression/governance.jsonl")[0].model_copy(
        update={"expected": {"alive": True, "nested": [False]}}
    )
    result = ExactEvaluator().evaluate(
        case,
        {"alive": 1, "nested": [0]},
        product_sha="abcdef1",
        dataset_hash=f"sha256:{'b' * 64}",
        seed=1,
    )

    assert result.passed is False


def test_baseline_comparison_rejects_changed_measurement_identity() -> None:
    baseline = _metadata()
    assert_baseline_compatible(_metadata(product_sha="fffffff"), baseline)

    with pytest.raises(GovernanceError, match="evaluator_version"):
        assert_baseline_compatible(_metadata(evaluator_version="2.0.0"), baseline)
    with pytest.raises(GovernanceError, match="dataset_hashes"):
        assert_baseline_compatible(
            _metadata(dataset_hashes={"routing": f"sha256:{'c' * 64}"}), baseline
        )
    with pytest.raises(GovernanceError, match="metrics_registry_hash"):
        assert_baseline_compatible(
            _metadata(metrics_registry_hash=f"sha256:{'1' * 64}"), baseline
        )
    with pytest.raises(GovernanceError, match="ruler_hashes"):
        assert_baseline_compatible(
            _metadata(ruler_hashes={"evaluators/exact.py": f"sha256:{'2' * 64}"}), baseline
        )
    with pytest.raises(GovernanceError, match="case_selection_hash"):
        assert_baseline_compatible(
            _metadata(case_selection_hash=f"sha256:{'3' * 64}"), baseline
        )
    with pytest.raises(GovernanceError, match="seed"):
        assert_baseline_compatible(_metadata(seed=8), baseline)


def test_subjective_metric_cannot_block_without_calibration(tmp_path: Path) -> None:
    registry = yaml.safe_load((EVAL_ROOT / "metrics-registry.yaml").read_text(encoding="utf-8"))
    registry["metrics"]["npc_persona_score"]["blocking"] = True
    registry["metrics"]["npc_persona_score"]["calibration"] = {
        "status": "approved",
        "dataset_hash": f"sha256:{'4' * 64}",
        "sample_size": 100,
        "agreement_kappa": 0.95,
    }
    path = tmp_path / "metrics.yaml"
    path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    with pytest.raises(GovernanceError, match="forbidden until SPEC-171"):
        load_metrics_registry(path)


def test_metric_definitions_have_auditable_denominators() -> None:
    registry = load_metrics_registry(EVAL_ROOT / "metrics-registry.yaml")

    for metric in registry.metrics.values():
        assert metric.unit
        assert metric.numerator
        assert metric.denominator
        assert isinstance(metric.exclusions, list)
    assert registry.metrics["npc_persona_score"].blocking is False


def test_run_result_cannot_silently_drop_eligible_cases() -> None:
    with pytest.raises(ValueError, match="every eligible case"):
        EvalRunResult(
            metadata=_metadata(),
            eligible_case_ids=["case.a", "case.b"],
            results=[],
            error_case_ids=["case.a"],
            skipped_case_ids=[],
        )


def test_run_result_selection_must_match_metadata_hash() -> None:
    with pytest.raises(ValueError, match="case_selection_hash"):
        EvalRunResult(
            metadata=_metadata(),
            eligible_case_ids=["case.a"],
            results=[],
            error_case_ids=["case.a"],
            skipped_case_ids=[],
        )

    with pytest.raises(ValueError, match="cannot be empty"):
        EvalRunResult(
            metadata=_metadata(case_selection_hash=f"sha256:{'0' * 64}"),
            eligible_case_ids=[],
            results=[],
        )
