"""Deterministic, fail-closed eval runner shared by component suites."""

from __future__ import annotations

import json
import os
import platform
import random
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from evals.core.adapters import AdapterCase, AdapterRegistry, default_registry
from evals.core.governance import GovernanceError, load_cases, load_metrics_registry, validate_repository
from evals.core.hashing import case_selection_hash, repository_identity
from evals.core.schemas import EvalCase, EvalCaseResult, EvalRunMetadata, EvalRunResult
from evals.evaluators import (
    ExactEvaluator,
    MemoryWriteEvaluator,
    NarrativeClaimEvaluator,
    ProjectionEvaluator,
    RetrievalEvaluator,
    RoutingEvaluator,
)


class EvalRunnerError(RuntimeError):
    """The harness cannot produce a trustworthy run."""


def _selected_datasets(
    eval_root: Path, manifest: dict[str, Any], requested: list[str] | None
) -> list[tuple[str, Path, str]]:
    locked = manifest.get("datasets") or {}
    selected = sorted(requested or locked)
    if not selected:
        raise EvalRunnerError("no locked dataset selected")
    rows: list[tuple[str, Path, str]] = []
    for relative in selected:
        normalized = PurePosixPath(relative.replace("\\", "/")).as_posix()
        if normalized not in locked:
            raise EvalRunnerError(f"dataset is not locked by governance: {relative}")
        rows.append((normalized, eval_root.joinpath(*PurePosixPath(normalized).parts), locked[normalized]))
    return rows


def _filter_cases(
    cases: list[tuple[EvalCase, str]],
    *,
    case_ids: set[str] | None,
    suites: set[str] | None,
    tags: set[str] | None,
) -> list[tuple[EvalCase, str]]:
    selected = [
        row
        for row in cases
        if (not case_ids or row[0].id in case_ids)
        and (not suites or row[0].suite in suites)
        and (not tags or tags.issubset(row[0].tags))
    ]
    if not selected:
        raise EvalRunnerError("case selection is empty")
    found = {case.id for case, _ in selected}
    missing = sorted((case_ids or set()) - found)
    if missing:
        raise EvalRunnerError("requested case ids not found: " + ", ".join(missing))
    return sorted(selected, key=lambda row: row[0].id)


def _metric_values(
    eligible: list[EvalCase], results: list[EvalCaseResult]
) -> dict[str, float]:
    result_by_id = {result.case_id: result for result in results}
    exact_cases = [case for case in eligible if case.oracle == "exact"]
    values: dict[str, float] = {}
    if exact_cases:
        values["exact_match"] = sum(
            result_by_id.get(case.id).metric_values.get("exact_match", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in exact_cases
        ) / len(exact_cases)
    projection_cases = [case for case in eligible if case.oracle == "projection"]
    if projection_cases:
        values["state_transition_pass_rate"] = sum(
            result_by_id.get(case.id).metric_values.get("state_transition_pass_rate", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in projection_cases
        ) / len(projection_cases)
    classification_cases = [case for case in eligible if case.oracle == "classification"]
    if classification_cases:
        values["route_accuracy"] = sum(
            result_by_id.get(case.id).metric_values.get("route_accuracy", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in classification_cases
        ) / len(classification_cases)
        target_cases = [
            case
            for case in classification_cases
            if isinstance(case.expected, dict) and "target" in case.expected
        ]
        if target_cases:
            values["target_accuracy"] = sum(
                result_by_id.get(case.id).metric_values.get("target_accuracy", 0.0)
                if result_by_id.get(case.id)
                else 0.0
                for case in target_cases
            ) / len(target_cases)
    memory_write_cases = [case for case in eligible if case.oracle == "memory_write"]
    if memory_write_cases:
        values["memory_write_precision"] = sum(
            result_by_id.get(case.id).metric_values.get("memory_write_precision", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in memory_write_cases
        ) / len(memory_write_cases)
    ranking_cases = [case for case in eligible if case.oracle == "ranking"]
    memory_ranked = [
        case
        for case in ranking_cases
        if case.suite == "memory_retrieval"
        and isinstance(case.expected, dict)
        and bool(case.expected.get("required_ids"))
    ]
    context_ranked = [
        case
        for case in ranking_cases
        if case.suite == "context_grounding"
        and isinstance(case.expected, dict)
        and bool(case.expected.get("required_ids"))
    ]
    for name in (
        "memory_recall_at_1",
        "memory_recall_at_3",
        "memory_recall_at_5",
        "memory_mrr",
    ):
        if memory_ranked:
            values[name] = sum(
                result_by_id.get(case.id).metric_values.get(name, 0.0)
                if result_by_id.get(case.id)
                else 0.0
                for case in memory_ranked
            ) / len(memory_ranked)
    if context_ranked:
        values["context_recall_at_5"] = sum(
            result_by_id.get(case.id).metric_values.get("context_recall_at_5", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in context_ranked
        ) / len(context_ranked)
    if ranking_cases:
        values["context_forbidden_leak_rate"] = sum(
            result_by_id.get(case.id).metric_values.get("context_forbidden_leak_rate", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in ranking_cases
        ) / len(ranking_cases)
        values["secret_leak_count"] = sum(
            result_by_id.get(case.id).metric_values.get("secret_leak_count", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in ranking_cases
        )
    context_cases = [case for case in ranking_cases if case.suite == "context_grounding"]
    if context_cases:
        values["context_token_budget_violation"] = sum(
            result_by_id.get(case.id).metric_values.get(
                "context_token_budget_violation", 0.0
            )
            if result_by_id.get(case.id)
            else 0.0
            for case in context_cases
        )
    narrative_cases = [case for case in eligible if case.oracle == "narrative_claim"]
    if narrative_cases:
        values["narrative_claim_accuracy"] = sum(
            result_by_id.get(case.id).metric_values.get("narrative_claim_accuracy", 0.0)
            if result_by_id.get(case.id)
            else 0.0
            for case in narrative_cases
        ) / len(narrative_cases)
        values["narrative_hard_contradictions"] = sum(
            result_by_id.get(case.id).metric_values.get(
                "narrative_hard_contradictions", 0.0
            )
            if result_by_id.get(case.id)
            else 0.0
            for case in narrative_cases
        )
        identity_cases = [case for case in narrative_cases if "identity" in case.tags]
        if identity_cases:
            values["npc_identity_errors"] = sum(
                result_by_id.get(case.id).metric_values.get("npc_identity_errors", 0.0)
                if result_by_id.get(case.id)
                else 0.0
                for case in identity_cases
            )
    return values


def _aggregates(cases: list[EvalCase], results: list[EvalCaseResult]) -> dict[str, Any]:
    result_by_id = {result.case_id: result for result in results}
    matrix: dict[str, dict[str, int]] = {}
    for case in cases:
        if case.oracle != "classification" or not isinstance(case.expected, dict):
            continue
        expected_route = str(case.expected.get("route") or "<missing>")
        result = result_by_id.get(case.id)
        actual_route = (
            str(result.actual.get("route") or "<missing>")
            if result and isinstance(result.actual, dict)
            else "<error>"
        )
        row = matrix.setdefault(expected_route, {})
        row[actual_route] = row.get(actual_route, 0) + 1
    aggregates: dict[str, Any] = {}
    if matrix:
        aggregates["route_confusion_matrix"] = matrix

    narrative_matrix: dict[str, dict[str, int]] = {}
    for case in cases:
        if case.oracle != "narrative_claim" or not isinstance(case.expected, dict):
            continue
        expected_reasons = case.expected.get("rejection_reasons") or []
        expected_label = "+".join(sorted(expected_reasons)) or "accepted"
        result = result_by_id.get(case.id)
        actual_reasons = (
            result.actual.get("rejection_reasons")
            if result and isinstance(result.actual, dict)
            else None
        )
        actual_label = (
            "+".join(sorted(str(reason) for reason in actual_reasons)) or "accepted"
            if isinstance(actual_reasons, list)
            else "<error>"
        )
        row = narrative_matrix.setdefault(expected_label, {})
        row[actual_label] = row.get(actual_label, 0) + 1
    if narrative_matrix:
        aggregates["narrative_reason_matrix"] = narrative_matrix

    layer_by_suite = {
        "memory_write": "store",
        "memory_retrieval": "retrieve",
        "context_grounding": "context",
        "generation_boundary": "generate",
    }
    layer_outcomes: dict[str, dict[str, int]] = {}
    for case in cases:
        layer = layer_by_suite.get(case.suite)
        if layer is None:
            continue
        outcome = layer_outcomes.setdefault(layer, {"passed": 0, "failed": 0, "error": 0})
        result = result_by_id.get(case.id)
        if result is None:
            outcome["error"] += 1
        elif result.passed:
            outcome["passed"] += 1
        else:
            outcome["failed"] += 1
    if layer_outcomes:
        aggregates["layer_outcomes"] = layer_outcomes
    return aggregates


def run_eval(
    root: Path,
    *,
    datasets: list[str] | None = None,
    case_ids: set[str] | None = None,
    suites: set[str] | None = None,
    tags: set[str] | None = None,
    seed: int = 7,
    run_id: str | None = None,
    registry: AdapterRegistry | None = None,
) -> EvalRunResult:
    """Execute selected locked cases without allowing provider-backed behavior."""

    root = root.resolve()
    eval_root = root / "evals"
    manifest = validate_repository(eval_root)
    dataset_rows = _selected_datasets(eval_root, manifest, datasets)
    loaded: list[tuple[EvalCase, str]] = []
    seen: set[str] = set()
    for relative, path, _ in dataset_rows:
        for case in load_cases(path):
            if case.id in seen:
                raise EvalRunnerError(f"duplicate case id across datasets: {case.id}")
            seen.add(case.id)
            loaded.append((case, relative))
    selected = _filter_cases(loaded, case_ids=case_ids, suites=suites, tags=tags)
    cases = [case for case, _ in selected]
    eligible_ids = [case.id for case in cases]
    try:
        product_sha, product_tree_hash, product_dirty = repository_identity(root)
    except RuntimeError as error:
        raise EvalRunnerError(str(error)) from error
    started_at = datetime.now(UTC)
    resolved_run_id = run_id or (
        f"eval-{started_at.strftime('%Y%m%dT%H%M%SZ')}-{product_sha[:8]}"
    )
    metadata = EvalRunMetadata(
        schema_version=1,
        evaluator_version=manifest["evaluator_version"],
        ruler_hashes=manifest["ruler_sources"],
        metrics_schema_version=manifest["metrics_schema_version"],
        metrics_registry_hash=manifest["metrics_registry"],
        product_sha=product_sha,
        product_tree_hash=product_tree_hash,
        product_dirty=product_dirty,
        dataset_hashes={relative: digest for relative, _, digest in dataset_rows},
        case_selection_hash=case_selection_hash(eligible_ids),
        seed=seed,
        started_at=started_at,
        provider=None,
        model=None,
        temperature=None,
        embedding=None,
        platform=f"{platform.system().casefold()}-py{platform.python_version()}",
    )
    adapters = registry or default_registry()
    evaluators = {
        "exact": ExactEvaluator(),
        "projection": ProjectionEvaluator(),
        "classification": RoutingEvaluator(),
        "memory_write": MemoryWriteEvaluator(),
        "ranking": RetrievalEvaluator(),
        "narrative_claim": NarrativeClaimEvaluator(),
    }
    random_state = random.getstate()
    random.seed(seed)
    results: list[EvalCaseResult] = []
    error_case_ids: list[str] = []
    diagnostics: dict[str, list[str]] = {}
    hard_failures: list[str] = []
    dataset_hash_by_path = {relative: digest for relative, _, digest in dataset_rows}

    previous_force_mock = os.environ.get("RPG_FORCE_MOCK")
    os.environ["RPG_FORCE_MOCK"] = "1"
    try:
        for case, relative in selected:
            try:
                evaluator = evaluators.get(case.oracle)
                if evaluator is None:
                    raise EvalRunnerError(f"no evaluator registered for oracle {case.oracle!r}")
                adapter_output = adapters.resolve(case.suite).execute(
                    AdapterCase.from_eval_case(case)
                )
                result = evaluator.evaluate(
                    case,
                    adapter_output.actual,
                    product_sha=product_sha,
                    dataset_hash=dataset_hash_by_path[relative],
                    seed=seed,
                )
                if adapter_output.diagnostics:
                    result = result.model_copy(
                        update={
                            "diagnostics": [
                                *result.diagnostics,
                                *adapter_output.diagnostics,
                            ]
                        }
                    )
                results.append(result)
                if result.diagnostics:
                    diagnostics[case.id] = list(result.diagnostics)
                if not result.passed:
                    hard_failures.append(f"case failed: {case.id}")
            except Exception as error:
                error_case_ids.append(case.id)
                diagnostics[case.id] = [f"{type(error).__name__}: {error}"]
                hard_failures.append(f"case error: {case.id}")
    finally:
        random.setstate(random_state)
        if previous_force_mock is None:
            os.environ.pop("RPG_FORCE_MOCK", None)
        else:
            os.environ["RPG_FORCE_MOCK"] = previous_force_mock

    metrics = _metric_values(cases, results)
    metrics_registry = load_metrics_registry(eval_root / "metrics-registry.yaml")
    for name, value in metrics.items():
        definition = metrics_registry.metrics.get(name)
        if definition is None or definition.blocking is not True or definition.hard_limit is None:
            continue
        violates = (
            value < definition.hard_limit
            if definition.direction == "higher"
            else value > definition.hard_limit
        )
        if violates:
            hard_failures.append(
                f"metric {name}={value:g} violates hard limit {definition.hard_limit:g}"
            )
    passed = not hard_failures and not error_case_ids and all(result.passed for result in results)
    return EvalRunResult(
        run_id=resolved_run_id,
        metadata=metadata,
        eligible_case_ids=eligible_ids,
        results=results,
        error_case_ids=error_case_ids,
        skipped_case_ids=[],
        case_diagnostics=diagnostics,
        metric_values=metrics,
        aggregates=_aggregates(cases, results),
        hard_failures=hard_failures,
        passed=passed,
    )


def write_run(result: EvalRunResult, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{result.run_id}.json"
    markdown_path = output_dir / f"{result.run_id}.md"
    if json_path.exists() or markdown_path.exists():
        raise EvalRunnerError(f"run artifact already exists: {result.run_id}")
    json_path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Eval run `{result.run_id}`",
        "",
        f"- Passed: `{result.passed}`",
        f"- Product SHA: `{result.metadata.product_sha}`",
        f"- Product tree hash: `{result.metadata.product_tree_hash}`",
        f"- Dirty worktree: `{result.metadata.product_dirty}`",
        f"- Evaluator: `{result.metadata.evaluator_version}`",
        f"- Eligible cases: `{len(result.eligible_case_ids)}`",
        f"- Dataset hashes: `{json.dumps(result.metadata.dataset_hashes, sort_keys=True)}`",
        f"- Ruler hashes: `{json.dumps(result.metadata.ruler_hashes, sort_keys=True)}`",
        "",
        "## Metrics",
        "",
    ]
    lines.extend(f"- `{name}`: `{value:.6f}`" for name, value in sorted(result.metric_values.items()))
    if result.aggregates:
        lines.extend(["", "## Aggregates", ""])
        lines.append("```json")
        lines.append(json.dumps(result.aggregates, ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
    lines.extend(["", "## Cases", ""])
    by_id = {case.case_id: case for case in result.results}
    for case_id in result.eligible_case_ids:
        case = by_id.get(case_id)
        status = "ERROR" if case_id in result.error_case_ids else "PASS" if case and case.passed else "FAIL"
        lines.append(f"- `{case_id}`: **{status}**")
        lines.extend(f"  - {item}" for item in result.case_diagnostics.get(case_id, []))
    if result.hard_failures:
        lines.extend(["", "## Hard failures", ""])
        lines.extend(f"- {failure}" for failure in result.hard_failures)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def load_run(path: Path) -> EvalRunResult:
    try:
        return EvalRunResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GovernanceError(f"invalid eval run {path}: {error}") from error


__all__ = ["EvalRunnerError", "load_run", "run_eval", "write_run"]
