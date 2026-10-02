"""Fail-closed baseline comparison for compatible deterministic eval runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evals.core.governance import (
    assert_baseline_compatible,
    assert_run_matches_repository,
    load_metrics_registry,
    validate_repository,
)
from evals.core.hashing import repository_identity
from evals.core.runner import load_run


def compare_runs(root: Path, current_path: Path, baseline_path: Path) -> dict[str, Any]:
    eval_root = root.resolve() / "evals"
    manifest = validate_repository(eval_root)
    current = load_run(current_path)
    baseline = load_run(baseline_path)
    assert_run_matches_repository(current.metadata, manifest)
    assert_run_matches_repository(baseline.metadata, manifest)
    assert_baseline_compatible(current.metadata, baseline.metadata)
    active_sha, active_tree_hash, active_dirty = repository_identity(root)
    if (
        current.metadata.product_sha != active_sha
        or current.metadata.product_tree_hash != active_tree_hash
        or current.metadata.product_dirty != active_dirty
    ):
        raise ValueError("current run does not identify the active product worktree")
    registry = load_metrics_registry(eval_root / "metrics-registry.yaml")
    deltas: dict[str, float] = {}
    regressions: list[str] = []
    for name in sorted(set(current.metric_values) | set(baseline.metric_values)):
        if name not in current.metric_values or name not in baseline.metric_values:
            regressions.append(f"metric missing from one run: {name}")
            continue
        value = current.metric_values[name]
        before = baseline.metric_values[name]
        deltas[name] = value - before
        definition = registry.metrics.get(name)
        if definition is None or definition.blocking is False:
            continue
        if definition.hard_limit is not None:
            failed_limit = (
                value < definition.hard_limit
                if definition.direction == "higher"
                else value > definition.hard_limit
            )
            if failed_limit:
                regressions.append(f"{name} violates hard limit")
        elif (definition.direction == "higher" and value < before) or (
            definition.direction == "lower" and value > before
        ):
            regressions.append(f"{name} regressed from baseline")
    if not current.passed:
        regressions.append("current run did not pass its own deterministic gates")
    return {
        "schema_version": 1,
        "baseline_run_id": baseline.run_id,
        "current_run_id": current.run_id,
        "baseline_product_sha": baseline.metadata.product_sha,
        "current_product_sha": current.metadata.product_sha,
        "deltas": deltas,
        "regressions": sorted(set(regressions)),
        "passed": not regressions,
    }


__all__ = ["compare_runs"]
