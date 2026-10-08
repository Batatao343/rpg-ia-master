"""SPEC-179: isolated, opt-in Jev experiment for canonical target and loot decisions.

The frozen corpus is experimental. This module never changes the product router,
protected evaluators, expected labels, or regression datasets.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Literal
from uuid import uuid4

from dotenv import load_dotenv

from evals.core.adapters import RoutingAdapter
from evals.core.hashing import repository_identity, sha256_file
from evals.experiments.jev_router_ab import (
    Budget, ExperimentBlocked, ROOT, _candidate, _capture_classify, _cases as routing_cases,
    _eligible,
    _error_result, _write_json,
)
from services import graph_resolver, npc_layers
from services.entity_identity import normalize_runtime_npc_ref, resolve_npc_entity_id, runtime_npc_aliases
from services.jev_decision import (
    ChoiceAnswer, ChoiceQuestion, DecisionRequest, DecisionState,
    JevDecisionBackend, JevError,
)


CORPUS = ROOT / "evals/experiments/data/spec179_corpus.jsonl"
CORPUS_LOCK = ROOT / "evals/experiments/data/spec179_corpus.sha256"
MAX_EXPERIMENT_TARGETS = 20  # Approved SPEC-179 gate; TypeSafe itself allows 255 Choice options.
MAX_PROVIDER_OPTIONS = 255
RECOVERY_RAW_SHA256 = "sha256:110e11597c79985b0b64a006ca09043a4e57e1a83ea6ee9caab674e3974ea836"
_RESUME_ONLY_PATHS = frozenset({
    "evals/experiments/jev_target_loot.py",
    "tests/test_jev_target_loot_experiment.py",
    "specs/SPEC-179-jev-target-loot-context-eval.md",
    "docs/spec179/README.md",
    "handoffs/SPEC-179-SOL-offline-review.md",
    "ESTADO_ATUAL.md", "ROADMAP.md",
    "project_index/manifest.json", "project_index/repo_graph.json",
})
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
LOOT_CRITERIA = {
    "TREASURE": "Abrir baú, vasculhar corpo ou recolher tesouro encontrado",
    "SHOP": "Comprar ou vender com um mercador",
    "CRAFT": "Fabricar ou forjar um item",
    "none": "A ação não envolve loot, comércio ou fabricação",
}


@dataclass(frozen=True)
class ExperimentCase:
    id: str
    measure: Literal["target", "loot_context"]
    input: dict[str, Any]
    expected: dict[str, str]
    source_case_id: str | None


@dataclass(frozen=True)
class TargetOptions:
    candidate_ids: tuple[str, ...]
    criteria: dict[str, str]
    aliases: dict[str, str | None]
    unrepresentable_reason: str | None
    filtered_hidden_count: int


def load_cases() -> tuple[list[ExperimentCase], str]:
    digest = sha256_file(CORPUS)
    if digest != CORPUS_LOCK.read_text(encoding="utf-8").strip():
        raise ExperimentBlocked("frozen SPEC-179 corpus hash mismatch")
    rows = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
    regression_ids = {case.id for case in routing_cases()[0]}
    cases: list[ExperimentCase] = []
    seen: set[str] = set()
    for row in rows:
        if set(row) != {"id", "measure", "input", "expected", "source_case_id"}:
            raise ExperimentBlocked("unexpected SPEC-179 corpus fields")
        case = ExperimentCase(**row)
        if (case.id in seen or case.measure not in ("target", "loot_context")
                or not isinstance(case.input, dict) or case.input.get("operation") != "route"
                or not isinstance(case.input.get("action"), str)
                or not isinstance(case.expected, dict)
                or set(case.expected) != {case.measure}
                or (case.source_case_id is not None and case.source_case_id not in regression_ids)):
            raise ExperimentBlocked(f"invalid SPEC-179 case {case.id}")
        seen.add(case.id)
        cases.append(case)
    if len(cases) != 14:
        raise ExperimentBlocked(f"expected 14 frozen SPEC-179 cases, got {len(cases)}")
    return cases, digest


def _visible(row: dict[str, Any]) -> bool:
    return (row.get("known_by_player", True) is not False
            and row.get("visibility", "public") not in {"hidden", "secret"}
            and row.get("in_scene", True) is not False
            and row.get("visible_to_player", True) is not False
            and row.get("status") not in {"morto", "fugiu", "dead", "fled"})


def _scene_visible(state: dict[str, Any], canonical: str) -> bool:
    if not graph_resolver.is_alive(canonical, state.get("world_projection")):
        return False
    position = (((state.get("combat") or {}).get("scene") or {}).get("positions") or {}).get(canonical) or {}
    return "player" not in (position.get("hidden_from") or [])


def _target_options(state: dict[str, Any]) -> TargetOptions:
    """Read only scene owners; never invent an ID or expose a hidden name."""
    options: dict[str, str] = {}
    alias_sets: dict[str, set[str]] = {}
    filtered = 0
    reason: str | None = None
    npcs = state.get("npcs") or {}
    party = state.get("party") or []

    for name in npc_layers.npcs_in_scene(state):
        row = npcs.get(name)
        loc = str((state.get("world") or {}).get("current_location_id") or "")
        home = str(row.get("home_location_id") or "") if isinstance(row, dict) else ""
        if (not isinstance(row, dict) or not npc_layers.is_in_scene(row)
                or (home and loc and home != loc)):
            row = next((member for member in party
                        if isinstance(member, dict) and member.get("name") == name
                        and member.get("active") and member.get("status", "ativo") == "ativo"), None)
        if not isinstance(row, dict):
            reason = "visible_actor_without_record"
            continue
        if not _visible(row):
            filtered += 1
            continue
        explicit = row.get("id")
        named_graph_id = resolve_npc_entity_id({"name": row.get("name")}, name)
        explicit_graph = graph_resolver.get_entity(str(explicit)) if explicit else None
        if named_graph_id and explicit_graph and named_graph_id != explicit:
            reason = "conflicting_canonical_identity"
            continue
        graph_id = resolve_npc_entity_id(row, name)
        # A runtime ID is valid only when no graph entity resolves the actor.
        # A misleading explicit ID must never override the source of truth.
        canonical = str(graph_id or explicit or "")
        if not canonical or not _IDENTIFIER.fullmatch(canonical) or canonical in {"none", "unknown"}:
            reason = "visible_actor_without_canonical_id"
            continue
        graph_row = graph_resolver.get_entity(canonical)
        if graph_row and (graph_row.get("type") != "npc" or
                          graph_row.get("visibility", "public") != "public"):
            filtered += 1
            continue
        if not _scene_visible(state, canonical):
            filtered += 1
            continue
        label = str(row.get("name") or name)
        options.setdefault(canonical, f"NPC presente: {label}")
        alias_sets.setdefault(canonical, set()).update(runtime_npc_aliases(name, row))

    for enemy in state.get("enemies") or []:
        if not isinstance(enemy, dict):
            continue
        if not _visible(enemy):
            filtered += 1
            continue
        canonical = str(enemy.get("id") or "")
        if not canonical or not _IDENTIFIER.fullmatch(canonical) or canonical in {"none", "unknown"}:
            reason = "visible_enemy_without_canonical_id"
            continue
        graph_row = graph_resolver.get_entity(canonical)
        if graph_row and graph_row.get("visibility", "public") != "public":
            filtered += 1
            continue
        if not _scene_visible(state, canonical):
            filtered += 1
            continue
        label = str(enemy.get("name") or canonical)
        options.setdefault(canonical, f"Inimigo presente: {label}")
        alias_sets.setdefault(canonical, set()).update(
            normalize_runtime_npc_ref(str(value))
            for value in (canonical, label, *(enemy.get("aliases") or []))
        )

    if len(options) > MAX_EXPERIMENT_TARGETS:
        reason = "experiment_target_cap_20"
    elif len(options) + 2 > MAX_PROVIDER_OPTIONS:
        reason = "provider_choice_cap_255"
    criteria = {key: options[key] for key in sorted(options)}
    criteria.update({
        "unknown": "Há alvo mencionado, mas ele não é um ID disponível ou é ambíguo",
        "none": "A ação não escolhe nenhuma pessoa ou inimigo como alvo",
    })
    if reason is None:
        try:
            ChoiceQuestion(instructions="Selecione o alvo canônico da ação.", criteria=criteria)
        except ValueError:
            reason = "criteria_not_representable"
    aliases: dict[str, str | None] = {}
    for canonical, values in alias_sets.items():
        for value in values:
            if value:
                aliases[value] = canonical if value not in aliases else (
                    canonical if aliases[value] == canonical else None
                )
    return TargetOptions(tuple(sorted(options)), criteria, aliases, reason, filtered)


def canonical_target(raw: str | None, options: TargetOptions) -> str:
    """Normalize the current router's label into an allowed scene ID."""
    if not raw:
        return "none"
    if raw in options.candidate_ids:
        return raw
    normalized = normalize_runtime_npc_ref(raw)
    if normalized in {"none", "unknown"}:
        return normalized
    return options.aliases.get(normalized) or "unknown"


def preflight() -> dict[str, Any]:
    cases, digest = load_cases()
    rows = []
    for case in cases:
        options = _target_options(case.input.get("state") or {}) if case.measure == "target" else None
        classifier_eligible, python_gate_route = _eligible(case)
        rows.append({
            "id": case.id, "measure": case.measure,
            "candidate_ids": list(options.candidate_ids) if options else [],
            "filtered_hidden_count": options.filtered_hidden_count if options else 0,
            "unrepresentable_reason": options.unrepresentable_reason if options else None,
            "classifier_eligible": classifier_eligible,
            "python_gate_route": python_gate_route,
        })
    return {"corpus_hash": digest, "cases": rows}


def _arm_a(case: ExperimentCase, options: TargetOptions | None, budget: Budget) -> dict[str, Any]:
    start = time.perf_counter()
    with _capture_classify(budget) as capture:
        try:
            actual = RoutingAdapter().execute(_candidate(case)).actual
        except Exception as exc:
            message = f"CLASSIFY failed for {case.id}: {type(exc).__name__}"
            raise ExperimentBlocked(message, _error_result(
                message, round((time.perf_counter() - start) * 1000), capture["attempts"],
            )) from exc
    attempts = capture["attempts"]
    success = next((attempt for attempt in attempts if attempt["outcome"] == "success"), None)
    if budget.exhausted or (attempts and success is None):
        message = f"CLASSIFY has no real decision for {case.id}"
        raise ExperimentBlocked(message, _error_result(
            message, round((time.perf_counter() - start) * 1000), attempts,
        ))
    if success is None:
        classifier_eligible, gate_route = _eligible(case)
        if classifier_eligible or gate_route != actual.get("route"):
            message = f"CLASSIFY unexpectedly skipped for {case.id}"
            raise ExperimentBlocked(message, _error_result(
                message, round((time.perf_counter() - start) * 1000), attempts,
            ))
    value = (canonical_target(actual.get("target"), options)
             if options is not None else actual.get("loot_context") or "none")
    if case.measure == "loot_context" and value not in LOOT_CRITERIA:
        value = "none"
    record = {
        "choice": value, "route": actual.get("route"),
        "confidence": capture["confidence"], "probabilities": "unavailable",
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "attempts": attempts,
        "provider": success["provider"] if success else "python_gate",
        "model": success["model"] if success else "unavailable",
        "usage": capture["usage_rows"] or "unavailable", "cost_usd": "unavailable",
        "error": None, "fatal_sanity_error": capture["fatal_sanity_error"],
    }
    if record["fatal_sanity_error"]:
        record["error"] = "CLASSIFY auth/quota/config failure during provider cascade"
        raise ExperimentBlocked(record["error"], record)
    return record


def _arm_b(
    case: ExperimentCase, options: TargetOptions | None,
    backend: JevDecisionBackend, budget: Budget, run_id: str,
) -> dict[str, Any]:
    value = case.input
    state = value.get("state") or {}
    world = state.get("world") or {}
    if case.measure == "target":
        assert options is not None and options.unrepresentable_reason is None
        question = ChoiceQuestion(
            instructions=("Selecione somente o ID canônico da pessoa/inimigo visível a quem "
                          "a ação se dirige. Use unknown para alvo fora das opções ou ambíguo; "
                          "use none quando não há alvo."),
            criteria=options.criteria,
        )
    else:
        question = ChoiceQuestion(
            instructions=("Classifique o contexto de loot da ação. Use TREASURE para "
                          "tesouro/baú/corpo, SHOP para compra/venda, CRAFT para fabricação, "
                          "none caso contrário."),
            criteria=LOOT_CRITERIA,
        )
    request = DecisionRequest(
        state=DecisionState(
            action=str(value.get("action") or ""),
            location_id=str(world.get("current_location_id") or world.get("current_location") or "Aethelgard"),
            in_combat=bool((state.get("combat") or {}).get("active")),
        ),
        questions={case.measure: question},
    )
    budget.consume()
    start = time.perf_counter()
    try:
        result = backend.decide(request, idempotency_key=f"{run_id}-{case.id}".replace("_", "-"))
    except JevError as exc:
        message = f"Jev {exc.code} for {case.id}"
        raise ExperimentBlocked(message, _error_result(
            message, round((time.perf_counter() - start) * 1000),
            [{"provider": "jev", "model": request.model, "outcome": exc.code}],
        )) from exc
    answer = result.answers[case.measure]
    if not isinstance(answer, ChoiceAnswer):
        raise ExperimentBlocked(f"Jev returned non-choice answer for {case.id}")
    record = {
        "choice": answer.choice, "confidence": answer.confidence,
        "probabilities": answer.probabilities,
        "latency_ms": round((time.perf_counter() - start) * 1000),
        "provider_latency_ms": result.latency_ms,
        "attempts": [{"provider": "jev", "model": result.model, "outcome": "success"}],
        "provider": "jev", "model": result.model,
        "usage": result.usage.model_dump() if result.usage else "unavailable",
        "cost_usd": result.cost_usd if result.cost_usd is not None else "unavailable",
        "error": None,
    }
    try:
        budget.record_cost(result.cost_usd)
    except ExperimentBlocked as exc:
        record["error"] = str(exc)
        raise ExperimentBlocked(str(exc), record) from exc
    return record


def score(raw: dict[str, Any], cases: list[ExperimentCase]) -> dict[str, Any]:
    """Read expected values only after the complete raw artifact is durable."""
    expected = {case.id: case.expected[case.measure] for case in cases}
    summary: dict[str, Any] = {"evidence_type": "experimental/development", "promotion": False}
    for measure in ("target", "loot_context"):
        rows = [row for row in raw["rows"] if row["measure"] == measure]
        paired = [row for row in rows if row["status"] == "paired"]
        unrepresentable = [row for row in rows if row["status"] == "unrepresentable"]
        allowed = lambda row: set(row["candidate_ids"]) | {"unknown", "none"} if measure == "target" else set(LOOT_CRITERIA)
        result: dict[str, Any] = {
            "semantic_count": len(rows), "representable_count": len(paired),
            "unrepresentable_count": len(unrepresentable),
            "unrepresentable": [{"case_id": row["case_id"], "reason": row["reason"]}
                                for row in unrepresentable],
            "fallback_count": sum("fallback" in row for row in unrepresentable),
            "divergences": [
                {"case_id": row["case_id"], "expected": expected[row["case_id"]],
                 "a": row["a"]["choice"], "b": row["b"]["choice"]}
                for row in paired if row["a"]["choice"] != row["b"]["choice"]
            ],
            "invalid_target_count": sum(
                row[arm]["choice"] not in allowed(row)
                for row in rows for arm in ("a", "b") if arm in row
            ),
        }
        for arm in ("a", "b"):
            correct = sum(row[arm]["choice"] == expected[row["case_id"]] for row in paired)
            result[arm] = {
                "correct": correct,
                "accuracy_representable": correct / len(paired) if paired else "unavailable",
                "coverage_adjusted_accuracy": correct / len(rows) if rows else "unavailable",
                "failure_rate": sum(row[arm]["error"] is not None for row in paired) / len(paired)
                if paired else "unavailable",
            }
        a_eligible = [row for row in rows if "a" in row and
                      expected[row["case_id"]] != "unrepresentable"]
        result["a"]["all_eligible_count"] = len(a_eligible)
        result["a"]["all_eligible_accuracy"] = (
            sum(row["a"]["choice"] == expected[row["case_id"]] for row in a_eligible)
            / len(a_eligible) if a_eligible else "unavailable"
        )
        summary[measure] = result
    return summary


def _required_calls(rows: list[dict[str, Any]]) -> int:
    return sum(
        (2 if row["unrepresentable_reason"] is None else 1)
        if row["classifier_eligible"] else
        (1 if row["unrepresentable_reason"] is None else 0)
        for row in rows
    )


def _assert_resume_code_drift(prior_sha: str, current_sha: str) -> None:
    """Only experiment and derived evidence may change between paired segments."""
    if prior_sha == current_sha:
        return
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", prior_sha, current_sha],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if ancestor.returncode:
        raise ExperimentBlocked("initial run commit is not an ancestor of resume")
    result = subprocess.run(
        ["git", "diff", "--name-only", prior_sha, current_sha, "--"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode or not set(result.stdout.splitlines()) <= _RESUME_ONLY_PATHS:
        raise ExperimentBlocked("product code changed between initial run and resume")


def _resume_raw(
    source_path: Path, cases: list[ExperimentCase], digest: str,
    prepared: list[dict[str, Any]], budget: Budget, current_sha: str,
    expected_raw_sha256: str,
) -> tuple[dict[str, Any], int]:
    """Resume only the zero-call Python-gate instrumentation failure from this run."""
    source_hash = sha256_file(source_path)
    if expected_raw_sha256 != RECOVERY_RAW_SHA256 or source_hash != expected_raw_sha256:
        raise ExperimentBlocked("resume raw hash differs from pre-registered recovery artifact")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    rows = source.get("rows") or []
    old_budget = source.get("budget") or {}
    if (source.get("status") != "blocked-by-provider" or
            source.get("corpus_hash") != digest or
            source.get("case_order") != [case.id for case in cases] or
            not rows or len(rows) > len(cases) or
            old_budget.get("max_calls") != budget.max_calls or
            old_budget.get("max_cost_usd") != budget.max_cost_usd or
            not isinstance(old_budget.get("calls"), int) or
            source.get("product_dirty") is not False or
            not source.get("product_sha") or not source.get("product_tree_hash") or
            budget.calls != 0 or budget.reported_cost_usd is not None):
        raise ExperimentBlocked("resume source or cumulative budget does not match frozen run")
    _assert_resume_code_drift(source["product_sha"], current_sha)
    for index, row in enumerate(rows):
        if (row.get("case_id") != cases[index].id or
                row.get("measure") != cases[index].measure or
                row.get("candidate_ids") != prepared[index]["candidate_ids"]):
            raise ExperimentBlocked("resume row does not match frozen corpus preflight")
    for row in rows[:-1]:
        if (row.get("status") not in {"paired", "unrepresentable"} or
                row.get("a", {}).get("error") is not None or
                (row["status"] == "paired" and
                 (row.get("b", {}).get("error") is not None or "b" not in row)) or
                (row["status"] == "unrepresentable" and "fallback" not in row)):
            raise ExperimentBlocked("resume prefix contains incomplete case")
    interrupted = rows[-1]
    if (interrupted.get("case_id") != "target.missing_id" or
            interrupted.get("status") != "unrepresentable" or
            interrupted.get("reason") != "visible_actor_without_canonical_id" or
            prepared[len(rows) - 1]["classifier_eligible"] or
            not interrupted.get("a", {}).get("error") or
            interrupted["a"].get("attempts") != [] or
            "b" in interrupted or "fallback" in interrupted):
        raise ExperimentBlocked("resume is restricted to the zero-call Python gate")
    observed_calls = sum(
        len(row.get(arm, {}).get("attempts") or [])
        for row in rows for arm in ("a", "b")
    )
    if observed_calls != old_budget["calls"] or old_budget.get("exhausted"):
        raise ExperimentBlocked("resume call ledger does not match persisted attempts")
    budget.calls = old_budget["calls"]
    budget.reported_cost_usd = old_budget.get("reported_cost_usd")
    if (budget.calls + _required_calls(prepared[len(rows) - 1:]) > budget.max_calls or
            (budget.calls + _required_calls(prepared[len(rows) - 1:]))
            * budget.reserved_per_call_usd > budget.max_cost_usd):
        raise ExperimentBlocked("remaining calls exceed cumulative approved cap")
    resumed = copy.deepcopy(source)
    resumed["resumed_from"] = {
        "run_id": source["run_id"], "raw_sha256": source_hash,
        "prior_product_sha": source["product_sha"],
        "prior_blocker": source.get("blocker"), "calls_before_resume": budget.calls,
    }
    resumed["rows"][-1]["a_before_resume"] = resumed["rows"][-1].pop("a")
    resumed.pop("blocker", None)
    resumed["status"] = "in_progress"
    return resumed, len(rows) - 1


def run(
    output_dir: Path, budget: Budget, *, resume_from: Path | None = None,
    resume_sha256: str | None = None,
) -> dict[str, Any]:
    local_env = ROOT / ".env"
    checkout_env = ROOT.parent.parent / ".env" if ROOT.parent.name == ".tmp" else local_env
    load_dotenv(local_env if local_env.exists() else checkout_env, override=False)
    if os.getenv("RPG_FORCE_MOCK") or os.getenv("RPG_NO_MOCK") or os.getenv("LLM_PROVIDER"):
        raise ExperimentBlocked("mock/no-mock/provider override invalidates current CLASSIFY cascade")
    cases, digest = load_cases()
    prepared = preflight()
    minimum = _required_calls(prepared["cases"])
    if minimum > budget.max_calls or minimum * budget.reserved_per_call_usd > budget.max_cost_usd:
        raise ExperimentBlocked(f"minimum {minimum} calls exceed approved cap")
    product_sha, tree_hash, dirty = repository_identity(ROOT)
    if dirty:
        raise ExperimentBlocked("SPEC-179 corpus and product code must be committed before live calls")
    if (resume_from is None) != (resume_sha256 is None):
        raise ExperimentBlocked("resume-from and resume-sha256 must be provided together")
    run_id = datetime.now(timezone.utc).strftime("SPEC-179-%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    if resume_from is None:
        raw: dict[str, Any] = {
            "run_id": run_id, "product_sha": product_sha, "product_tree_hash": tree_hash,
            "product_dirty": dirty, "corpus_hash": digest,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "case_order": [case.id for case in cases], "budget": asdict(budget),
            "rows": [], "status": "in_progress",
        }
        start_index = 0
    else:
        raw, start_index = _resume_raw(resume_from, cases, digest, prepared["cases"], budget,
                                       product_sha, resume_sha256)
        raw["run_id"] = run_id
        raw["product_sha"] = product_sha
        raw["product_tree_hash"] = tree_hash
        raw["started_at"] = datetime.now(timezone.utc).isoformat()
        raw["budget"] = asdict(budget)
    output_dir.mkdir(parents=True, exist_ok=False)
    path = output_dir / "raw.json"
    _write_json(path, raw)
    try:
        with JevDecisionBackend(max_retries=0) as backend:
            for index, (case, prepared_row) in enumerate(zip(cases, prepared["cases"], strict=True)):
                if index < start_index:
                    continue
                options = _target_options(case.input.get("state") or {}) if case.measure == "target" else None
                if index < len(raw["rows"]):
                    row = raw["rows"][index]
                else:
                    row = {
                        "case_id": case.id, "measure": case.measure,
                        "candidate_ids": prepared_row["candidate_ids"],
                        "filtered_hidden_count": prepared_row["filtered_hidden_count"],
                    }
                    raw["rows"].append(row)
                if prepared_row["unrepresentable_reason"]:
                    row.update(status="unrepresentable", reason=prepared_row["unrepresentable_reason"])
                    try:
                        row["a"] = _arm_a(case, options, budget)
                    except ExperimentBlocked as exc:
                        row["a"] = exc.record or _error_result(str(exc), 0, [])
                        raise
                    row["fallback"] = {
                        **row["a"], "provider": "current_router_fallback",
                        "attempts": [], "fallback_from": "a",
                    }
                    _write_json(path, raw)
                    continue
                row["status"] = "in_progress"
                try:
                    row["a"] = _arm_a(case, options, budget)
                except ExperimentBlocked as exc:
                    row["a"] = exc.record or _error_result(str(exc), 0, [])
                    raise
                _write_json(path, raw)
                try:
                    row["b"] = _arm_b(case, options, backend, budget, run_id)
                except ExperimentBlocked as exc:
                    row["b"] = exc.record or _error_result(str(exc), 0, [])
                    raise
                row["status"] = "paired"
                _write_json(path, raw)
        raw["status"] = "complete"
    except (ExperimentBlocked, JevError) as exc:
        raw["status"] = "blocked-by-provider"
        raw["blocker"] = str(exc)
    finally:
        raw["budget"] = asdict(budget)
        _write_json(path, raw)
    if raw["status"] == "complete":
        _write_json(output_dir / "summary.json", score(raw, cases))
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--resume-sha256")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-cost-usd", type=float)
    args = parser.parse_args()
    if args.preflight:
        print(json.dumps(preflight(), ensure_ascii=False, indent=2))
        return
    if args.output_dir is None or args.max_calls is None or args.max_cost_usd is None:
        parser.error("live execution requires output-dir, max-calls and max-cost-usd")
    if args.max_calls <= 0 or args.max_cost_usd <= 0:
        parser.error("call and spending caps must be positive")
    result = run(
        args.output_dir, Budget(max_calls=args.max_calls, max_cost_usd=args.max_cost_usd),
        resume_from=args.resume_from, resume_sha256=args.resume_sha256,
    )
    print(json.dumps({"run_id": result["run_id"], "status": result["status"], "calls": result["budget"]["calls"]}))


if __name__ == "__main__":
    main()
