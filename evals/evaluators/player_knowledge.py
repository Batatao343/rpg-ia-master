"""Deterministic evaluator for the player-facing knowledge Codex (SPEC-206).

Two fixture-authored contracts:

* ``project``: the projected Codex must contain exactly the expected entries per
  category, with the expected ``knowledge_kind`` (and optional stamp fields) per
  entry and per note, consistent ``meta.counts``, at least the expected number of
  redactions, an empty product leak oracle and no forbidden fragment. Forbidden
  fragments are checked here with an evaluator-owned normalization (accent fold,
  casefold, collapsed whitespace), independent of the product scanner.
* ``oracle_mutation``: a deliberately leaked Codex must be flagged by the product
  oracle with exactly the expected problem classes (``<branch>:<kind>``).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult

CATEGORIES = ("locations", "factions", "characters", "creatures", "secrets")
KNOWLEDGE_KINDS = frozenset({"fact", "report", "rumor", "suspicion", "perception"})
_STAMP_FIELDS = frozenset(
    {"knowledge_kind", "certainty", "source_kind", "source_ref", "label", "stale"}
)
_NOTE_FIELDS = frozenset({"text", "knowledge_kind", "certainty", "source_kind", "label"})
_PROJECT_KEYS = frozenset({"entries", "notes", "min_redactions", "forbidden_fragments"})
_MUTATION_KEYS = frozenset({"oracle_problem_classes"})
_WS = re.compile(r"\s+")


def fold_text(value: str) -> str:
    """Evaluator-owned normalization: no accents, casefold, single spaces."""

    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WS.sub(" ", stripped.casefold()).strip()


def problem_class(problem: str) -> str:
    return ":".join(problem.split(":")[:2])


def _validate_stamp(expected: Any, allowed: frozenset[str], where: str) -> None:
    if not isinstance(expected, dict) or not expected:
        raise ValueError(f"{where} must be a non-empty object")
    if not set(expected).issubset(allowed) or "knowledge_kind" not in expected:
        raise ValueError(f"{where} has an invalid stamp contract")
    if expected["knowledge_kind"] not in KNOWLEDGE_KINDS:
        raise ValueError(f"{where} knowledge_kind is outside the taxonomy")


def _validate_project_expected(expected: dict[str, Any]) -> None:
    if not {"entries", "forbidden_fragments"}.issubset(expected) or not set(expected).issubset(
        _PROJECT_KEYS
    ):
        raise ValueError("player knowledge project expected has an invalid contract")
    entries = expected["entries"]
    if not isinstance(entries, dict) or set(entries) != set(CATEGORIES):
        raise ValueError("expected entries must declare all five categories")
    for category, rows in entries.items():
        if not isinstance(rows, dict):
            raise ValueError(f"expected entries.{category} must be an object")
        for key, stamp in rows.items():
            _validate_stamp(stamp, _STAMP_FIELDS, f"entries.{category}.{key}")
    notes = expected.get("notes") or {}
    if not isinstance(notes, dict):
        raise ValueError("expected notes must be an object")
    for anchor, rows in notes.items():
        category, _, key = anchor.partition("/")
        if category not in CATEGORIES or key not in entries[category]:
            raise ValueError(f"expected note anchor is not an expected entry: {anchor}")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"expected notes for {anchor} must be a non-empty list")
        for row in rows:
            _validate_stamp(row, _NOTE_FIELDS, f"notes.{anchor}")
            if not isinstance(row.get("text"), str):
                raise ValueError(f"expected note for {anchor} requires text")
    minimum = expected.get("min_redactions", 0)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 0:
        raise ValueError("min_redactions must be a non-negative integer")
    fragments = expected["forbidden_fragments"]
    if not isinstance(fragments, list) or any(
        not isinstance(item, str) or not item.strip() for item in fragments
    ):
        raise ValueError("forbidden_fragments must be non-empty strings")
    if len(fragments) != len(set(fragments)):
        raise ValueError("forbidden_fragments must be unique")


def _stamp_matches(actual: Any, expected: dict[str, Any]) -> bool:
    return isinstance(actual, dict) and all(
        type(actual.get(field)) is type(value) and actual.get(field) == value
        for field, value in expected.items()
    )


class PlayerKnowledgeEvaluator:
    """Score leak, taxonomy and count contracts of the player Codex projection."""

    evaluator_id = "player_knowledge_contract"
    evaluator_version = EVALUATOR_VERSION

    def evaluate(
        self,
        case: EvalCase,
        actual: Any,
        *,
        product_sha: str,
        dataset_hash: str,
        seed: int,
    ) -> EvalCaseResult:
        if case.oracle != "player_knowledge":
            raise ValueError(f"player knowledge evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        if not isinstance(case.expected, dict) or not isinstance(case.input, dict):
            raise ValueError("player knowledge case requires object input and expected")
        if not isinstance(actual, dict) or not isinstance(actual.get("oracle_problems"), list):
            raise ValueError("player knowledge actual requires oracle_problems")
        operation = case.input.get("operation") or "project"
        if actual.get("operation") != operation:
            raise ValueError("player knowledge actual operation differs from the case")
        diagnostics: list[str] = []
        metrics: dict[str, float] = {}

        if operation == "oracle_mutation":
            if set(case.expected) != _MUTATION_KEYS:
                raise ValueError("oracle mutation expected has an invalid contract")
            expected_classes = case.expected["oracle_problem_classes"]
            if not isinstance(expected_classes, list) or any(
                not isinstance(item, str) or item.count(":") != 1 for item in expected_classes
            ):
                raise ValueError("oracle_problem_classes must be <branch>:<kind> strings")
            actual_classes = sorted({problem_class(str(p)) for p in actual["oracle_problems"]})
            passed = actual_classes == sorted(set(expected_classes))
            metrics["player_knowledge_oracle_detection"] = 1.0 if passed else 0.0
            if not passed:
                diagnostics.append(
                    f"oracle classes {actual_classes} differ from {sorted(expected_classes)}"
                )
        elif operation == "project":
            expected = case.expected
            _validate_project_expected(expected)
            entries = actual.get("entries")
            if not isinstance(entries, dict) or not isinstance(actual.get("codex_json"), str):
                raise ValueError("player knowledge actual requires entries and codex_json")

            failures: list[str] = []
            hits = 0
            total = 0
            for category in CATEGORIES:
                actual_rows = entries.get(category)
                if not isinstance(actual_rows, dict):
                    raise ValueError(f"actual entries.{category} must be an object")
                expected_rows = expected["entries"][category]
                if set(actual_rows) != set(expected_rows):
                    failures.append(
                        f"{category} entries {sorted(actual_rows)} != {sorted(expected_rows)}"
                    )
                for key, stamp in expected_rows.items():
                    total += 1
                    got = actual_rows.get(key)
                    if isinstance(got, dict) and got.get("knowledge_kind") == stamp["knowledge_kind"]:
                        hits += 1
                    if not _stamp_matches(got, stamp):
                        failures.append(f"{category}/{key} stamp differs from fixture")

            actual_notes = actual.get("notes")
            if not isinstance(actual_notes, dict):
                raise ValueError("player knowledge actual notes must be an object")
            expected_notes = expected.get("notes") or {}
            if set(actual_notes) != set(expected_notes):
                failures.append(
                    f"note anchors {sorted(actual_notes)} != {sorted(expected_notes)}"
                )
            for anchor, rows in expected_notes.items():
                got_rows = actual_notes.get(anchor) or []
                if len(got_rows) != len(rows):
                    failures.append(f"{anchor} has {len(got_rows)} notes, expected {len(rows)}")
                for index, row in enumerate(rows):
                    total += 1
                    got = got_rows[index] if index < len(got_rows) else None
                    if isinstance(got, dict) and got.get("knowledge_kind") == row["knowledge_kind"]:
                        hits += 1
                    if not _stamp_matches(got, row):
                        failures.append(f"{anchor} note {index} differs from fixture")

            counts = actual.get("counts")
            lengths = actual.get("list_lengths")
            consistent = (
                isinstance(counts, dict)
                and isinstance(lengths, dict)
                and all(
                    counts.get(category) == lengths.get(category) == len(entries[category])
                    for category in CATEGORIES
                )
            )
            if not consistent:
                failures.append("meta.counts differs from the projected lists")

            redactions = actual.get("redactions")
            minimum = expected.get("min_redactions", 0)
            if isinstance(redactions, bool) or not isinstance(redactions, int) or redactions < minimum:
                failures.append(f"redactions {redactions!r} below fixture minimum {minimum}")

            folded = fold_text(actual["codex_json"])
            survived = [
                fragment
                for fragment in expected["forbidden_fragments"]
                if fold_text(fragment) in folded
            ]
            leaked = bool(actual["oracle_problems"]) or bool(survived)
            if actual["oracle_problems"]:
                failures.append(
                    "product leak oracle flagged the projection: "
                    + ", ".join(problem_class(str(p)) for p in actual["oracle_problems"])
                )
            if survived:
                failures.append(f"{len(survived)} forbidden fragment(s) survived projection")

            metrics["player_knowledge_leak_count"] = 1.0 if leaked else 0.0
            metrics["player_knowledge_count_consistency"] = 1.0 if consistent else 0.0
            if total:
                metrics["player_knowledge_kind_accuracy"] = hits / total
            diagnostics.extend(failures)
            passed = not failures
        else:
            raise ValueError(f"unsupported player knowledge operation: {operation!r}")

        return EvalCaseResult(
            case_id=case.id,
            suite=case.suite,
            passed=passed,
            actual=actual,
            expected=case.expected,
            metric_values=metrics,
            diagnostics=diagnostics,
            evaluator_id=self.evaluator_id,
            evaluator_version=self.evaluator_version,
            product_sha=product_sha,
            dataset_hash=dataset_hash,
            seed=seed,
            started_at=started_at,
            duration_ms=(perf_counter() - started) * 1000,
        )
