"""Deterministic evaluator for the player-safe dossiers (SPEC-211).

Fixture-authored contracts over the JSON the dossier endpoint serves:

* ``project``: the dossier payload must list exactly the expected ids per section,
  keep every fixture-labelled forbidden fragment out of the serialized JSON
  (evaluator-owned accent-fold normalization), pass both product oracles
  (allowlist and SPEC-206 leak oracle), honour per-creature tier key
  presence/absence and optional path assertions.
* ``paired_project``: two saves identical except for one hidden entity must
  yield byte-identical payloads (hidden is indistinguishable from nonexistent).
* ``oracle_mutation``: a deliberately corrupted payload must be flagged by the
  product oracles with exactly the fixture-labelled problem classes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from evals.core.schemas import EVALUATOR_VERSION, EvalCase, EvalCaseResult
from evals.evaluators.player_knowledge import fold_text, problem_class

SECTIONS = ("npcs", "locations", "factions", "secrets", "bestiary")
_PROJECT_KEYS = frozenset({"ids", "forbidden_fragments", "creatures", "assertions"})
_PAIRED_KEYS = frozenset({"identical", "forbidden_fragments"})
_MUTATION_KEYS = frozenset({"problem_classes"})
_ASSERT_OPS = frozenset({"equals", "not_equals", "absent", "one_of"})
_MISSING = object()


def private_class(problem: str) -> str:
    return "private:" + problem.split(":")[0]


def leak_class(problem: str) -> str:
    return "leak:" + problem_class(problem)


def resolve_path(value: Any, path: str) -> Any:
    """Dotted path into dicts/lists; returns ``_MISSING`` when any step is absent."""

    current = value
    for part in path.split("."):
        if isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def _validate_fragments(expected: dict[str, Any]) -> None:
    fragments = expected["forbidden_fragments"]
    if not isinstance(fragments, list) or any(
        not isinstance(item, str) or not item.strip() for item in fragments
    ):
        raise ValueError("forbidden_fragments must be non-empty strings")
    if len(fragments) != len(set(fragments)):
        raise ValueError("forbidden_fragments must be unique")


def _validate_project(expected: dict[str, Any]) -> None:
    if not {"ids", "forbidden_fragments"}.issubset(expected) or not set(expected).issubset(
        _PROJECT_KEYS
    ):
        raise ValueError("dossier project expected has an invalid contract")
    ids = expected["ids"]
    if not isinstance(ids, dict) or set(ids) != set(SECTIONS):
        raise ValueError("expected ids must declare all five sections")
    for section, rows in ids.items():
        if not isinstance(rows, list) or any(not isinstance(i, str) for i in rows):
            raise ValueError(f"expected ids.{section} must be a list of strings")
    _validate_fragments(expected)
    for creature, spec in (expected.get("creatures") or {}).items():
        if not isinstance(spec, dict) or set(spec) != {"tier", "present", "absent"}:
            raise ValueError(f"creatures.{creature} needs tier, present and absent")
        if not isinstance(spec["tier"], int) or isinstance(spec["tier"], bool):
            raise ValueError(f"creatures.{creature}.tier must be an integer")
        if not isinstance(spec["present"], list) or not isinstance(spec["absent"], list):
            raise ValueError(f"creatures.{creature} present/absent must be lists")
        if set(spec["present"]) & set(spec["absent"]):
            raise ValueError(f"creatures.{creature} present and absent overlap")
    for item in expected.get("assertions") or []:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("assertion requires a path")
        ops = set(item) - {"path"}
        if len(ops) != 1 or not ops.issubset(_ASSERT_OPS):
            raise ValueError("assertion requires exactly one of equals/not_equals/absent/one_of")
        if "one_of" in ops and not isinstance(item["one_of"], list):
            raise ValueError("one_of must be a list")


def _check_assertion(payload: Any, item: dict[str, Any]) -> bool:
    got = resolve_path(payload, item["path"])
    if "absent" in item:
        return (got is _MISSING) == bool(item["absent"])
    if got is _MISSING:
        return False
    if "equals" in item:
        return type(got) is type(item["equals"]) and got == item["equals"]
    if "not_equals" in item:
        return got != item["not_equals"]
    return got in item["one_of"]


class DossierLeakEvaluator:
    """Score leak, tier-key and indistinguishability contracts of dossiers."""

    evaluator_id = "dossier_leak_contract"
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
        if case.oracle != "dossier_leak":
            raise ValueError(f"dossier leak evaluator cannot evaluate {case.oracle!r}")
        started_at = datetime.now(UTC)
        started = perf_counter()
        if not isinstance(case.expected, dict) or not isinstance(case.input, dict):
            raise ValueError("dossier leak case requires object input and expected")
        if not isinstance(actual, dict):
            raise ValueError("dossier leak actual must be an object")
        operation = case.input.get("operation") or "project"
        if actual.get("operation") != operation:
            raise ValueError("dossier leak actual operation differs from the case")
        diagnostics: list[str] = []
        metrics: dict[str, float] = {}

        if operation == "oracle_mutation":
            if set(case.expected) != _MUTATION_KEYS:
                raise ValueError("oracle mutation expected has an invalid contract")
            expected_classes = case.expected["problem_classes"]
            if not isinstance(expected_classes, list) or any(
                not isinstance(item, str) or ":" not in item for item in expected_classes
            ):
                raise ValueError("problem_classes must be <oracle>:<kind> strings")
            private = actual.get("private_problems")
            leak = actual.get("leak_problems")
            if not isinstance(private, list) or not isinstance(leak, list):
                raise ValueError("oracle mutation actual requires problem lists")
            actual_classes = sorted(
                {private_class(str(p)) for p in private} | {leak_class(str(p)) for p in leak}
            )
            passed = actual_classes == sorted(set(expected_classes))
            metrics["dossier_oracle_detection"] = 1.0 if passed else 0.0
            if not passed:
                diagnostics.append(
                    f"oracle classes {actual_classes} differ from {sorted(expected_classes)}"
                )
        elif operation == "paired_project":
            expected = case.expected
            if set(expected) != _PAIRED_KEYS or expected["identical"] is not True:
                raise ValueError("paired expected must declare identical true and fragments")
            _validate_fragments(expected)
            blobs = actual.get("payload_jsons")
            if (
                not isinstance(blobs, list)
                or len(blobs) != 2
                or not all(isinstance(b, str) for b in blobs)
            ):
                raise ValueError("paired actual requires two payload_jsons")
            identical = blobs[0] == blobs[1]
            folded = [fold_text(blob) for blob in blobs]
            survived = [
                fragment
                for fragment in expected["forbidden_fragments"]
                if any(fold_text(fragment) in text for text in folded)
            ]
            if not identical:
                diagnostics.append("hidden save payload differs from the nonexistent save")
            if survived:
                diagnostics.append(f"{len(survived)} forbidden fragment(s) survived projection")
            metrics["dossier_leak_count"] = 1.0 if survived else 0.0
            metrics["dossier_indistinguishability"] = 1.0 if identical else 0.0
            passed = identical and not survived
        elif operation == "project":
            expected = case.expected
            _validate_project(expected)
            payload = actual.get("payload")
            blob = actual.get("payload_json")
            ids = actual.get("ids")
            if (
                not isinstance(payload, dict)
                or not isinstance(blob, str)
                or not isinstance(ids, dict)
            ):
                raise ValueError("dossier actual requires payload, payload_json and ids")
            private = actual.get("private_problems")
            leak = actual.get("leak_problems")
            if not isinstance(private, list) or not isinstance(leak, list):
                raise ValueError("dossier actual requires oracle problem lists")
            failures: list[str] = []
            for section in SECTIONS:
                if sorted(ids.get(section) or []) != sorted(expected["ids"][section]):
                    failures.append(
                        f"{section} ids {sorted(ids.get(section) or [])}"
                        f" != {sorted(expected['ids'][section])}"
                    )
            if private:
                failures.append(
                    "allowlist oracle flagged: "
                    + ", ".join(sorted({private_class(str(p)) for p in private}))
                )
            if leak:
                failures.append(
                    "leak oracle flagged: "
                    + ", ".join(sorted({leak_class(str(p)) for p in leak}))
                )
            folded = fold_text(blob)
            survived = [f for f in expected["forbidden_fragments"] if fold_text(f) in folded]
            if survived:
                failures.append(f"{len(survived)} forbidden fragment(s) survived projection")
            creatures = expected.get("creatures") or {}
            if creatures:
                hits = 0
                actual_creatures = actual.get("creatures")
                if not isinstance(actual_creatures, dict):
                    raise ValueError("dossier actual requires creatures")
                for creature, spec in creatures.items():
                    got = actual_creatures.get(creature)
                    keys = set(got.get("keys") or []) if isinstance(got, dict) else set()
                    ok = (
                        isinstance(got, dict)
                        and got.get("tier") == spec["tier"]
                        and set(spec["present"]) <= keys
                        and not (set(spec["absent"]) & keys)
                    )
                    hits += 1 if ok else 0
                    if not ok:
                        failures.append(f"creature {creature} keys differ from tier contract")
                metrics["dossier_tier_key_accuracy"] = hits / len(creatures)
            for item in expected.get("assertions") or []:
                if not _check_assertion(payload, item):
                    failures.append(f"assertion failed: {item}")
            metrics["dossier_leak_count"] = 1.0 if (private or leak or survived) else 0.0
            diagnostics.extend(failures)
            passed = not failures
        else:
            raise ValueError(f"unsupported dossier leak operation: {operation!r}")

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
