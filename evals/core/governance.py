"""Fail-closed governance checks for eval datasets, metrics and baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic import ValidationError

from evals.core.hashing import sha256_file
from evals.core.schemas import (
    EVALUATOR_VERSION,
    EvalCase,
    EvalCaseResult,
    EvalRunMetadata,
    EvalRunResult,
    MetricsRegistry,
)


class GovernanceError(RuntimeError):
    """The eval run is not trustworthy enough to execute or compare."""


REQUIRED_PROTECTED_PATHS = frozenset(
    {
        "evals/core",
        "evals/evaluators",
        "evals/__main__.py",
        "evals/datasets/regression",
        "evals/manifest.lock.json",
        "evals/metrics-registry.yaml",
        "evals/protected-paths.txt",
        "evals/eval-case.schema.json",
        "evals/eval-result.schema.json",
        "evals/eval-run.schema.json",
        "evals/eval-run-result.schema.json",
        "web/e2e/contracts",
    }
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GovernanceError(f"cannot read valid JSON from {path}") from error
    if not isinstance(value, dict):
        raise GovernanceError(f"expected JSON object in {path}")
    return value


def load_cases(path: Path) -> list[EvalCase]:
    """Load JSONL strictly, rejecting blank/duplicate/invalid cases."""

    cases: list[EvalCase] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise GovernanceError(f"cannot read dataset {path}") from error
    if not lines:
        raise GovernanceError(f"dataset is empty: {path}")
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise GovernanceError(f"blank JSONL record at {path}:{line_number}")
        try:
            case = EvalCase.model_validate_json(line)
        except (ValidationError, ValueError) as error:
            raise GovernanceError(f"invalid eval case at {path}:{line_number}: {error}") from error
        if case.id in seen:
            raise GovernanceError(f"duplicate case id {case.id!r} in {path}")
        seen.add(case.id)
        cases.append(case)
    return cases


def load_metrics_registry(path: Path) -> MetricsRegistry:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return MetricsRegistry.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise GovernanceError(f"invalid metrics registry {path}: {error}") from error


def load_protected_paths(path: Path) -> tuple[str, ...]:
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise GovernanceError(f"cannot read protected paths {path}") from error
    values = tuple(row.strip().rstrip("/") for row in rows if row.strip() and not row.startswith("#"))
    if not values:
        raise GovernanceError("protected paths list cannot be empty")
    missing = REQUIRED_PROTECTED_PATHS - set(values)
    if missing:
        raise GovernanceError("protected paths removed required controls: " + ", ".join(sorted(missing)))
    return tuple(sorted(set(values) | REQUIRED_PROTECTED_PATHS))


def protected_changes(changed_paths: list[str], protected: tuple[str, ...]) -> list[str]:
    """Return protected repo-relative paths touched by an optimization task."""

    hits: list[str] = []
    for raw in changed_paths:
        path = PurePosixPath(raw.replace("\\", "/")).as_posix().lstrip("./")
        folded = path.casefold()
        if any(
            folded == prefix.casefold() or folded.startswith(f"{prefix.casefold()}/")
            for prefix in protected
        ):
            hits.append(path)
    return sorted(set(hits))


def assert_optimization_paths_allowed(changed_paths: list[str], protected_file: Path) -> None:
    hits = protected_changes(changed_paths, load_protected_paths(protected_file))
    if hits:
        raise GovernanceError(
            "optimization task changed protected eval paths; use a separate evaluator-change task: "
            + ", ".join(hits)
        )


def assert_baseline_compatible(current: EvalRunMetadata, baseline: EvalRunMetadata) -> None:
    """Reject comparisons whose measurement identity changed."""

    mismatches: list[str] = []
    if current.schema_version != baseline.schema_version:
        mismatches.append("run schema_version")
    if current.evaluator_version != baseline.evaluator_version:
        mismatches.append("evaluator_version")
    if current.ruler_hashes != baseline.ruler_hashes:
        mismatches.append("ruler_hashes")
    if current.metrics_schema_version != baseline.metrics_schema_version:
        mismatches.append("metrics_schema_version")
    if current.metrics_registry_hash != baseline.metrics_registry_hash:
        mismatches.append("metrics_registry_hash")
    if current.dataset_hashes != baseline.dataset_hashes:
        mismatches.append("dataset_hashes")
    if current.case_selection_hash != baseline.case_selection_hash:
        mismatches.append("case_selection_hash")
    for field in ("seed", "provider", "model", "temperature", "embedding", "platform"):
        if getattr(current, field) != getattr(baseline, field):
            mismatches.append(field)
    if mismatches:
        raise GovernanceError("baseline is incompatible: " + ", ".join(mismatches))


def assert_run_matches_repository(
    metadata: EvalRunMetadata, manifest: dict[str, Any]
) -> None:
    """Require a stored run to describe the ruler currently validated on disk."""

    mismatches: list[str] = []
    if metadata.evaluator_version != manifest.get("evaluator_version"):
        mismatches.append("evaluator_version")
    if metadata.ruler_hashes != manifest.get("ruler_sources"):
        mismatches.append("ruler_hashes")
    if metadata.metrics_schema_version != manifest.get("metrics_schema_version"):
        mismatches.append("metrics_schema_version")
    if metadata.metrics_registry_hash != manifest.get("metrics_registry"):
        mismatches.append("metrics_registry_hash")
    locked_datasets = manifest.get("datasets") or {}
    if not metadata.dataset_hashes or any(
        locked_datasets.get(path) != digest for path, digest in metadata.dataset_hashes.items()
    ):
        mismatches.append("dataset_hashes")
    if mismatches:
        raise GovernanceError(
            "eval run does not match active repository ruler: " + ", ".join(mismatches)
        )


def _schema_payloads() -> dict[str, dict[str, Any]]:
    return {
        "eval-case.schema.json": EvalCase.model_json_schema(),
        "eval-result.schema.json": EvalCaseResult.model_json_schema(),
        "eval-run.schema.json": EvalRunMetadata.model_json_schema(),
        "eval-run-result.schema.json": EvalRunResult.model_json_schema(),
    }


def _ruler_hashes(eval_root: Path) -> dict[str, str]:
    files = list(
        path
        for directory in (eval_root / "core", eval_root / "evaluators")
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    files.append(eval_root / "__main__.py")
    files = sorted(files)
    if not files:
        raise GovernanceError("no ruler source files found")
    return {path.relative_to(eval_root).as_posix(): sha256_file(path) for path in files}


def write_schema_files(eval_root: Path) -> None:
    for name, payload in _schema_payloads().items():
        (eval_root / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def build_lock(eval_root: Path, datasets: list[Path]) -> dict[str, Any]:
    registry = load_metrics_registry(eval_root / "metrics-registry.yaml")
    if registry.evaluator_version != EVALUATOR_VERSION:
        raise GovernanceError("metrics registry evaluator_version does not match source")
    locked: dict[str, str] = {}
    for path in sorted(datasets):
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(eval_root.resolve()).as_posix()
        except ValueError as error:
            raise GovernanceError(f"dataset must live below {eval_root}: {path}") from error
        if "holdout" in PurePosixPath(relative).parts:
            raise GovernanceError("private holdout cannot be locked in the public repository")
        load_cases(resolved)
        locked[relative] = sha256_file(resolved)
    if not locked:
        raise GovernanceError("at least one public dev/regression dataset is required")
    return {
        "schema_version": 1,
        "evaluator_version": EVALUATOR_VERSION,
        "metrics_schema_version": registry.schema_version,
        "metrics_registry": sha256_file(eval_root / "metrics-registry.yaml"),
        "ruler_sources": _ruler_hashes(eval_root),
        "datasets": locked,
    }


def write_lock(eval_root: Path, datasets: list[Path]) -> None:
    write_schema_files(eval_root)
    payload = build_lock(eval_root, datasets)
    (eval_root / "manifest.lock.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_repository(eval_root: Path) -> dict[str, Any]:
    """Validate every frozen input before a runner may execute."""

    if (eval_root / "datasets" / "holdout").exists():
        raise GovernanceError("public evals/datasets/holdout is forbidden")
    manifest = _load_json(eval_root / "manifest.lock.json")
    if manifest.get("schema_version") != 1:
        raise GovernanceError("unsupported manifest schema_version")
    if manifest.get("evaluator_version") != EVALUATOR_VERSION:
        raise GovernanceError("manifest evaluator_version does not match source")
    registry = load_metrics_registry(eval_root / "metrics-registry.yaml")
    if manifest.get("metrics_schema_version") != registry.schema_version:
        raise GovernanceError("manifest metrics_schema_version does not match registry")
    expected_registry_hash = manifest.get("metrics_registry")
    actual_registry_hash = sha256_file(eval_root / "metrics-registry.yaml")
    if expected_registry_hash != actual_registry_hash:
        raise GovernanceError("metrics registry hash mismatch")
    if manifest.get("ruler_sources") != _ruler_hashes(eval_root):
        raise GovernanceError("ruler source hash mismatch")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or not datasets:
        raise GovernanceError("manifest must lock at least one dataset")
    for relative, expected_hash in datasets.items():
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise GovernanceError("manifest dataset entries must be string pairs")
        parts = PurePosixPath(relative).parts
        if not parts or ".." in parts or "holdout" in parts:
            raise GovernanceError(f"unsafe or private dataset path in manifest: {relative}")
        path = eval_root.joinpath(*parts)
        if sha256_file(path) != expected_hash:
            raise GovernanceError(f"dataset hash mismatch: {relative}")
        load_cases(path)
    for name, expected in _schema_payloads().items():
        if _load_json(eval_root / name) != expected:
            raise GovernanceError(f"stale generated schema: {name}")
    load_protected_paths(eval_root / "protected-paths.txt")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "lock"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dataset", action="append", type=Path, default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    eval_root = args.root.resolve() / "evals"
    try:
        if args.action == "lock":
            datasets = [path if path.is_absolute() else args.root / path for path in args.dataset]
            write_lock(eval_root, datasets)
            print(f"locked {len(datasets)} dataset(s)")
        else:
            manifest = validate_repository(eval_root)
            print(f"eval governance valid: {len(manifest['datasets'])} dataset(s)")
    except GovernanceError as error:
        print(f"eval governance failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
