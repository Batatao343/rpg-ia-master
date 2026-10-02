"""Canonical, fail-closed schemas for deterministic eval inputs and outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from evals.core.hashing import case_selection_hash


EVALUATOR_VERSION = "1.6.0"

OracleKind = Literal[
    "exact",
    "projection",
    "classification",
    "memory_write",
    "ranking",
    "narrative_claim",
    "property",
    "judge",
]
CaseSource = Literal["manual", "regression", "canonical", "synthetic"]
MetricKind = Literal["deterministic", "ranking", "classification", "llm_judge"]
MetricDirection = Literal["higher", "lower"]
BlockingPolicy = bool | Literal["after_baseline"]


class EvalCase(BaseModel):
    """One immutable public dev/regression case."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=3, pattern=r"^[a-z0-9][a-z0-9._-]+$")
    suite: str = Field(min_length=1)
    description: str = Field(min_length=1)
    fixture: str | None = None
    input: Any
    expected: Any
    oracle: OracleKind
    tags: list[str] = Field(default_factory=list)
    source: CaseSource
    created_from: str | None = None


class EvalCaseResult(BaseModel):
    """Addressable result emitted by a versioned evaluator."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    suite: str
    passed: bool
    actual: Any
    expected: Any
    metric_values: dict[str, float] = Field(default_factory=dict)
    diagnostics: list[str] = Field(default_factory=list)
    evaluator_id: str
    evaluator_version: str
    product_sha: str
    dataset_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    seed: int
    started_at: datetime
    duration_ms: float = Field(ge=0)


class EvalRunMetadata(BaseModel):
    """Compatibility identity for one eval run or stored baseline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    evaluator_version: str
    ruler_hashes: dict[str, str]
    metrics_schema_version: int = Field(ge=1)
    metrics_registry_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    product_sha: str = Field(min_length=7)
    product_tree_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    product_dirty: bool
    dataset_hashes: dict[str, str]
    case_selection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    seed: int
    started_at: datetime
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    embedding: str | None = None
    platform: str | None = None

    @model_validator(mode="after")
    def validate_dataset_hashes(self) -> "EvalRunMetadata":
        if not self.dataset_hashes:
            raise ValueError("at least one dataset hash is required")
        for value in self.dataset_hashes.values():
            if not value.startswith("sha256:") or len(value) != 71:
                raise ValueError("dataset hashes must use sha256:<64 hex>")
            try:
                int(value.removeprefix("sha256:"), 16)
            except ValueError as error:
                raise ValueError("dataset hash is not hexadecimal") from error
        if not self.ruler_hashes:
            raise ValueError("at least one ruler source hash is required")
        for value in self.ruler_hashes.values():
            if not value.startswith("sha256:") or len(value) != 71:
                raise ValueError("ruler hashes must use sha256:<64 hex>")
        return self


class JudgeCalibration(BaseModel):
    """Human-labelled meta-eval evidence required before a judge can block."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["approved"]
    dataset_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    sample_size: int = Field(ge=30)
    agreement_kappa: float = Field(ge=0.7, le=1.0)


class MetricDefinition(BaseModel):
    """A metric with an auditable denominator and exclusion policy."""

    model_config = ConfigDict(extra="forbid")

    direction: MetricDirection
    kind: MetricKind
    blocking: BlockingPolicy
    unit: str = Field(min_length=1)
    numerator: str = Field(min_length=1)
    denominator: str = Field(min_length=1)
    exclusions: list[str]
    hard_limit: float | None = None
    calibration: JudgeCalibration | None = None

    @model_validator(mode="after")
    def keep_subjective_metrics_informational_until_calibrated(self) -> "MetricDefinition":
        if self.kind == "llm_judge" and self.blocking is not False:
            raise ValueError("blocking llm_judge metrics are forbidden until SPEC-171 meta-eval")
        return self


class MetricsRegistry(BaseModel):
    """Versioned registry used by reports and compatibility gates."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    evaluator_version: str
    metrics: dict[str, MetricDefinition]

    @model_validator(mode="after")
    def require_metrics(self) -> "MetricsRegistry":
        if not self.metrics:
            raise ValueError("metrics registry cannot be empty")
        return self


class EvalRunResult(BaseModel):
    """Run-level accounting that makes skipped/error cases part of the denominator."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(
        default="unassigned",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    metadata: EvalRunMetadata
    eligible_case_ids: list[str]
    results: list[EvalCaseResult]
    error_case_ids: list[str] = Field(default_factory=list)
    skipped_case_ids: list[str] = Field(default_factory=list)
    case_diagnostics: dict[str, list[str]] = Field(default_factory=dict)
    metric_values: dict[str, float] = Field(default_factory=dict)
    aggregates: dict[str, Any] = Field(default_factory=dict)
    hard_failures: list[str] = Field(default_factory=list)
    passed: bool = False

    @model_validator(mode="after")
    def require_complete_case_accounting(self) -> "EvalRunResult":
        eligible = self.eligible_case_ids
        if not eligible:
            raise ValueError("eligible case ids cannot be empty")
        if len(eligible) != len(set(eligible)):
            raise ValueError("eligible case ids must be unique")
        result_ids = [result.case_id for result in self.results]
        accounted = result_ids + self.error_case_ids + self.skipped_case_ids
        if len(accounted) != len(set(accounted)):
            raise ValueError("a case cannot be accounted more than once")
        if set(accounted) != set(eligible):
            raise ValueError("every eligible case must be result, error or explicit skip")
        if case_selection_hash(eligible) != self.metadata.case_selection_hash:
            raise ValueError("eligible case ids do not match metadata case_selection_hash")
        dataset_hashes = set(self.metadata.dataset_hashes.values())
        for result in self.results:
            if result.product_sha != self.metadata.product_sha:
                raise ValueError("case result product_sha disagrees with run metadata")
            if result.evaluator_version != self.metadata.evaluator_version:
                raise ValueError("case result evaluator_version disagrees with run metadata")
            if result.dataset_hash not in dataset_hashes:
                raise ValueError("case result dataset_hash is absent from run metadata")
            if result.seed != self.metadata.seed:
                raise ValueError("case result seed disagrees with run metadata")
        if not set(self.case_diagnostics).issubset(eligible):
            raise ValueError("case diagnostics must reference eligible cases")
        if not set(self.error_case_ids).issubset(self.case_diagnostics):
            raise ValueError("every error case must have diagnostics")
        expected_passed = (
            not self.hard_failures
            and not self.error_case_ids
            and not self.skipped_case_ids
            and all(result.passed for result in self.results)
        )
        if self.passed != expected_passed:
            raise ValueError("run passed flag disagrees with complete case accounting")
        return self
