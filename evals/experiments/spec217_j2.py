"""SPEC-217 J2: confirmatory paired A/B on the FROZEN corpus, run ONCE.

Arm A = the current router (Python gates -> CLASSIFY, live). Arm B = the frozen
J1b hybrid policy (``frozen_j1b_request`` + ``frozen_loot_decision``): Python
gates, then the Jev; when the Jev is not confident/representable B uses the
CLASSIFY answer of the *same* case and replicate (latency = Jev + CLASSIFY).

Blocking runner requirements (handoffs/SPEC-217-ASTRA-J1-review.md and
handoffs/SPEC-238-ASTRA-review.md):

* single-run FROZEN mode: corpus/oracle/structure digests checked before any
  call; a durable marker + ledger stamp refuse a second run without an explicit
  owner authorization string;
* shared on-disk ledger (``spec217-j1/ledger.json``): ``j2_calls`` <= 100 and
  spec total <= 190, incremented *before* every network attempt of either arm;
* stop (no score) on any Jev error and on any CLASSIFY attempt that is not a
  single first-candidate success (fallback, retry, structured regeneration);
  a second provider slot inside one CLASSIFY call is refused *before* network;
* 4 sanity calls (2 per arm) on a case outside both corpora;
* seeded pairing over 3 replicates (case order and arm order declared in raw);
* R9.1-R9.7 are pure functions over raw observations.

Only this module reads the FROZEN corpus. Production is untouched
(``RPG_JEV_ROUTER_MODE`` default ``off``).

Run: ``uv run python -m evals.experiments.spec217_j2 --phase run --env-file <.env>``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone, UTC
from fractions import Fraction
from pathlib import Path
from typing import Any
from collections.abc import Callable, Mapping

from evals.core.hashing import repository_identity, sha256_file
from evals.experiments import jev_router_hybrid as hybrid
from evals.experiments import spec238_loot as loot
from evals.experiments.jev_router_ab import _write_json
from evals.experiments.jev_router_hybrid import (
    ROOT,
    Case,
    CorpusError,
    digest_of,
    extract_verbs,
    normalize_action,
    percentile,
    scene_view,
)
from evals.experiments.spec217_j1 import LEDGER, BudgetExhausted, _answers
from services.jev_decision import DecisionBackend, DecisionRequest, JevError

FROZEN_CORPUS = ROOT / "evals/experiments/data/spec217_frozen.jsonl"
FROZEN_LOCK = ROOT / "evals/experiments/data/spec217_frozen.sha256"
FROZEN_ORACLE = ROOT / "evals/experiments/data/spec217_frozen_loot_oracle.json"
FROZEN_ORACLE_LOCK = ROOT / "evals/experiments/data/spec217_frozen_loot_oracle.sha256"
FROZEN_ORACLE_SHA256 = "sha256:d9c860ecad9e06bb2ccf38ad98b04d7fa3d8aa228326a8821be3ea546845c38d"
RUNS = ROOT / "evals/runs/jev-router-hybrid"
MARKER = RUNS / "J2_STARTED.json"
J2_CALL_CAP = 100
TOTAL_CALL_CAP = 190
REPLICATES = 3
SANITY_CALLS_PER_ARM = 2
PAIRING_SEED = "SPEC-217-J2"
R9_1_MARGIN = Fraction(1, 40)  # 2.5 pp
R9_1_MAX_PAIRED_LOSSES = 1
R9_4_MIN_P50_GAIN_MS = 500.0
R9_4_MAX_P95_RATIO = 1.10
R9_7_REFERENCE = "oracle"  # sealed sidecar (SPEC-238 R8, option 1)

# A synthetic case outside both corpora (checked at run time); it must reach
# CLASSIFY (probe) so both arms spend a real call.
SANITY_CASE = Case(
    id="spec217.j2.sanity.observe",
    kind="route",
    input={
        "operation": "route",
        "action": "Examino as inscrições gastas no marco de pedra",
        "state": {"world": {"current_location": "Aethelgard"}},
    },
    expected={},
    python_gate=False,
    critical=None,
)


class ProviderStop(RuntimeError):
    """R10: a provider error/fallback/retry/regeneration; the run stops without score."""


# ---------------------------------------------------------------------------
# FROZEN inputs (single process reads the corpus)
# ---------------------------------------------------------------------------


def load_frozen_cases(
    path: Path = FROZEN_CORPUS, lock: Path = FROZEN_LOCK
) -> tuple[list[Case], str]:
    digest = sha256_file(path)
    if digest != lock.read_text(encoding="utf-8").strip() or digest != hybrid.FROZEN_SHA256:
        raise CorpusError("SPEC-217 FROZEN corpus hash mismatch")
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("split") != "frozen":
            raise CorpusError("non-FROZEN row in FROZEN corpus")
        cases.append(
            Case(
                id=row["id"],
                kind=row["kind"],
                input=row["input"],
                expected=row["expected"],
                python_gate=bool(row["python_gate"]),
                critical=row.get("critical"),
            )
        )
    return cases, digest


def load_frozen_oracle(
    path: Path = FROZEN_ORACLE, lock: Path = FROZEN_ORACLE_LOCK
) -> tuple[dict[str, str], str]:
    digest = sha256_file(path)
    if digest != lock.read_text(encoding="utf-8").strip() or digest != FROZEN_ORACLE_SHA256:
        raise CorpusError("SPEC-217 FROZEN loot oracle hash mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    labels = {case_id: row["loot_source"] for case_id, row in data["labels"].items()}
    if any(value not in loot.LOOT_SOURCES for value in labels.values()):
        raise CorpusError("FROZEN loot oracle has an invalid source")
    return labels, digest


def verify_frozen_structure() -> dict[str, str]:
    """Refuse unless the J1 and J1b freezes match the code exactly."""
    j1 = hybrid.structure_digest(hybrid.FROZEN_J1_POLICY)
    j1b = loot.structure_digest(loot.FROZEN_J1B_POLICY)
    if j1 != hybrid.FROZEN_J1_STRUCTURE_DIGEST:
        raise CorpusError("J1 structure digest does not match the freeze")
    if j1b != loot.FROZEN_J1B_STRUCTURE_DIGEST:
        raise CorpusError("J1b structure digest does not match the freeze")
    if loot.FROZEN_J1B_LOCATION_FEATURES:
        raise CorpusError("J2 requires location features OFF (Astra emenda)")
    return {
        "j1_structure_digest": j1,
        "j1b_structure_digest": j1b,
        "variant_id": loot.FROZEN_J1B_POLICY.variant_id,
    }


def sanity_outside_corpora(sanity: Case, *corpora: list[Case]) -> None:
    action = normalize_action(hybrid._fold(sanity.input["action"]))
    for cases in corpora:
        for case in cases:
            if (
                case.id == sanity.id
                or normalize_action(hybrid._fold(str(case.input.get("action") or ""))) == action
            ):
                raise CorpusError("sanity case overlaps a corpus")


# ---------------------------------------------------------------------------
# Ledger + single-run guard
# ---------------------------------------------------------------------------


class J2Ledger:
    """Shared SPEC-217 ledger; J2 counter capped at 100, spec total at 190."""

    def __init__(
        self, path: Path = LEDGER, j2_cap: int = J2_CALL_CAP, total_cap: int = TOTAL_CALL_CAP
    ) -> None:
        self.path, self.j2_cap, self.total_cap = path, j2_cap, total_cap

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"spec": "SPEC-217", "j1_calls": 0, "total_calls": 0, "entries": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def remaining(self) -> int:
        data = self.read()
        return max(
            0, min(self.j2_cap - data.get("j2_calls", 0), self.total_cap - data["total_calls"])
        )

    def consume(self, phase: str, case_id: str, provider: str) -> int:
        data = self.read()
        if data.get("j2_calls", 0) >= self.j2_cap or data["total_calls"] >= self.total_cap:
            raise BudgetExhausted("SPEC-217 J2 external call cap reached")
        data["j2_calls"] = data.get("j2_calls", 0) + 1
        data["total_calls"] += 1
        data["total_cap"] = self.total_cap
        data["entries"].append(
            {
                "n": data["total_calls"],
                "phase": phase,
                "case_id": case_id,
                "provider": provider,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        data["reserved_usd"] = round(data["total_calls"] * hybrid.RESERVED_USD_PER_CALL, 2)
        _write_json(self.path, data)
        return data["total_calls"]

    def stamp_j2(self, run_id: str) -> None:
        data = self.read()
        data.setdefault("j2_runs", []).append(
            {"run_id": run_id, "at": datetime.now(UTC).isoformat()}
        )
        _write_json(self.path, data)


def claim_single_run(
    marker: Path, ledger: J2Ledger, run_id: str, owner_rerun_authorization: str | None = None
) -> None:
    """R8: the FROZEN is used once; a second run needs an explicit owner string."""
    previous = marker.exists() or bool(ledger.read().get("j2_runs"))
    if previous and not owner_rerun_authorization:
        raise CorpusError("J2 already ran on the FROZEN corpus; a rerun needs owner authorization")
    marker.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else {"runs": []}
    history["runs"].append(
        {
            "run_id": run_id,
            "at": datetime.now(UTC).isoformat(),
            "owner_rerun_authorization": owner_rerun_authorization,
        }
    )
    _write_json(marker, history)
    ledger.stamp_j2(run_id)


# ---------------------------------------------------------------------------
# Pairing plan (declared in raw before any call)
# ---------------------------------------------------------------------------


def pairing_plan(
    eligible_ids: list[str], seed: str = PAIRING_SEED, replicates: int = REPLICATES
) -> list[dict[str, Any]]:
    plan = []
    for number in range(1, replicates + 1):
        rng = random.Random(f"{seed}|replicate-{number}")
        order = sorted(eligible_ids)
        rng.shuffle(order)
        plan.append(
            {
                "replicate": number,
                "order": [{"case_id": cid, "first_arm": rng.choice(("a", "b"))} for cid in order],
            }
        )
    return plan


def required_calls(eligible: int, replicates: int = REPLICATES) -> int:
    return 2 * SANITY_CALLS_PER_ARM + 2 * eligible * replicates


# ---------------------------------------------------------------------------
# CLASSIFY stop rule (pure) and live arm A
# ---------------------------------------------------------------------------


def classify_violation(attempts: list[Mapping[str, Any]]) -> str | None:
    """R10: exactly one attempt, first candidate, first try, success."""
    if not attempts:
        return "no_attempt"
    if len(attempts) != 1:
        return "extra_attempt"
    attempt = attempts[0]
    if attempt.get("outcome") != "success":
        return f"outcome_{attempt.get('outcome')}"
    if attempt.get("fell_back"):
        return "fell_back"
    if int(attempt.get("attempt_index") or 0) > 0:
        return "retry"
    return None


class _SlotBudget:
    """``Budget`` duck type for ``_capture_classify``: one ledger call per CLASSIFY.

    A second provider slot in the same CLASSIFY invocation (fallback to another
    candidate or a structured regeneration) is refused before any network I/O.
    """

    def __init__(self, ledger: J2Ledger, phase: str, case_id: str) -> None:
        self.ledger, self.phase, self.case_id = ledger, phase, case_id
        self.exhausted = False
        self.slots = 0
        self.refused = False
        self.call_n: int | None = None

    def consume(self) -> None:
        if self.slots >= 1:
            self.refused = True
            raise ProviderStop("second CLASSIFY slot refused (fallback/regeneration)")
        try:
            self.call_n = self.ledger.consume(self.phase, self.case_id, "classify")
        except BudgetExhausted:
            self.exhausted = True
            raise
        self.slots += 1


def live_classify(ledger: J2Ledger) -> Callable[[Case, str], dict[str, Any]]:
    """Arm A: the current router through ``RoutingAdapter``, captured attempt by attempt."""
    import llm_setup
    from agents.router import RouterDecision
    from evals.core.adapters import RoutingAdapter
    from evals.experiments.jev_router_ab import _candidate, _capture_classify

    def run(case: Case, phase: str) -> dict[str, Any]:
        budget = _SlotBudget(ledger, phase, case.id)
        decision: dict[str, Any] = {}
        error: str | None = None
        actual: dict[str, Any] = {}
        with _capture_classify(budget) as capture:  # type: ignore[arg-type]
            inner = llm_setup.RoutedLLM.invoke

            def record(self: Any, value: Any) -> Any:
                result = inner(self, value)
                if isinstance(result, RouterDecision):
                    decision.update(
                        route=result.route.value,
                        target=result.target,
                        loot_context=result.loot_context,
                        confidence=result.confidence,
                    )
                return result

            llm_setup.RoutedLLM.invoke = record
            start = time.perf_counter()
            try:
                actual = RoutingAdapter().execute(_candidate(case)).actual
            except Exception as exc:  # noqa: BLE001 - recorded, then stop
                error = f"{type(exc).__name__}"
            finally:
                latency = round((time.perf_counter() - start) * 1000)
                llm_setup.RoutedLLM.invoke = inner
        attempts = capture["attempts"]
        record_row = {
            "route": actual.get("route"),
            "target_raw": actual.get("target"),
            "loot_source_effective": actual.get("loot_context"),
            "loot_context_raw": decision.get("loot_context"),
            "decision_route": decision.get("route"),
            "decision_target": decision.get("target"),
            "confidence": decision.get("confidence"),
            "latency_ms": latency,
            "attempts": attempts,
            "call_n": budget.call_n,
            "usage": capture["usage_rows"] or "unavailable",
            "cost_usd": "unavailable",
        }
        violation = (
            "budget_exhausted"
            if budget.exhausted
            else "second_slot_refused"
            if budget.refused
            else error
            or classify_violation(attempts)
            or (None if decision else "no_structured_decision")
        )
        record_row["error"] = violation
        if violation:
            raise ProviderStop(json.dumps(record_row, ensure_ascii=False, default=str))
        return record_row

    return run


def jev_call(
    backend: DecisionBackend, ledger: J2Ledger, run_id: str
) -> Callable[[Case, str], dict[str, Any]]:
    """Arm B network call: the exact frozen J1b request (location features off)."""

    def run(case: Case, phase: str) -> dict[str, Any]:
        request: DecisionRequest = loot.frozen_j1b_request(case.input)
        row: dict[str, Any] = {
            "request_digest": digest_of(request.wire_body()),
            "questions": sorted(request.questions),
        }
        row["call_n"] = ledger.consume(phase, case.id, "jev")
        start = time.perf_counter()
        try:
            result = backend.decide(request, idempotency_key=f"spec217-j2-{run_id}-{row['call_n']}")
            answers = _answers(result.answers)
        except JevError as exc:
            row["error"] = getattr(exc, "code", "jev_error")
            row["latency_ms"] = round((time.perf_counter() - start) * 1000)
            raise ProviderStop(json.dumps(row, ensure_ascii=False)) from exc
        missing = set(request.questions) - set(answers)
        row.update(
            {
                "answers": answers,
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "provider_latency_ms": result.latency_ms,
                "model": result.model,
                "usage": result.usage.model_dump() if result.usage else "unavailable",
                "cost_usd": result.cost_usd if result.cost_usd is not None else "unavailable",
                "error": f"missing_answers:{sorted(missing)}" if missing else None,
            }
        )
        if missing:
            raise ProviderStop(json.dumps(row, ensure_ascii=False))
        return row

    return run


# ---------------------------------------------------------------------------
# Runner (network injected; offline-testable)
# ---------------------------------------------------------------------------


def _features(case: Case) -> dict[str, Any]:
    state = case.input.get("state") or {}
    view = scene_view(state)
    return {
        "verbs": list(extract_verbs(str(case.input.get("action") or ""))),
        "in_combat": bool((state.get("combat") or {}).get("active")),
        "target_status": view.target_status,
        "candidates": [actor.id for actor in view.actors],
    }


def run_j2(
    *,
    eligible: list[Case],
    gates: Mapping[str, str],
    sanity: Case,
    classify: Callable[[Case, str], dict[str, Any]],
    jev: Callable[[Case, str], dict[str, Any]],
    ledger: J2Ledger,
    output_dir: Path,
    meta: Mapping[str, Any],
    seed: str = PAIRING_SEED,
) -> dict[str, Any]:
    """Sanity (A,B,A,B) then 3 seeded replicates; raw durable after every call."""
    output_dir.mkdir(parents=True, exist_ok=False)
    raw_path = output_dir / "raw.json"
    by_id = {case.id: case for case in eligible}
    plan = pairing_plan(sorted(by_id), seed)
    raw: dict[str, Any] = {
        **meta,
        "stage": "J2",
        "status": "in_progress",
        "started_at": datetime.now(UTC).isoformat(),
        "pairing_seed": seed,
        "pairing_plan": plan,
        "replicates": REPLICATES,
        "eligible_ids": sorted(by_id),
        "gate_routes": dict(sorted(gates.items())),
        "sanity_case": {"id": sanity.id, "input": sanity.input},
        "sanity": [],
        "rows": [],
    }
    _write_json(raw_path, raw)
    try:
        for _ in range(SANITY_CALLS_PER_ARM):
            for arm, call in (("a", classify), ("b", jev)):
                entry: dict[str, Any] = {"arm": arm}
                raw["sanity"].append(entry)
                entry.update(call(sanity, "j2-sanity"))
                _write_json(raw_path, raw)
        for replicate in plan:
            for gate_id, route in sorted(gates.items()):
                raw["rows"].append(
                    {
                        "replicate": replicate["replicate"],
                        "case_id": gate_id,
                        "python_gate": True,
                        "a": {"route": route, "calls": 0},
                        "b": {"route": route, "calls": 0},
                    }
                )
            for item in replicate["order"]:
                case = by_id[item["case_id"]]
                row = {
                    "replicate": replicate["replicate"],
                    "case_id": case.id,
                    "python_gate": False,
                    "first_arm": item["first_arm"],
                    **_features(case),
                }
                raw["rows"].append(row)
                arms = ("a", "b") if item["first_arm"] == "a" else ("b", "a")
                for arm in arms:
                    row[arm] = {"pending": True}
                    row[arm] = (classify if arm == "a" else jev)(
                        case, f"j2-r{replicate['replicate']}"
                    )
                    _write_json(raw_path, raw)
        raw["status"] = "complete"
    except BudgetExhausted as exc:
        raw["status"] = "stopped-budget"
        raw["blocker"] = str(exc)
    except ProviderStop as exc:
        raw["status"] = "blocked-by-provider"
        raw["blocker"] = str(exc)
    finally:
        raw["finished_at"] = datetime.now(UTC).isoformat()
        raw["ledger_after"] = {k: v for k, v in ledger.read().items() if k != "entries"}
        _write_json(raw_path, raw)
    return raw


# ---------------------------------------------------------------------------
# Observations + R9 (pure, from raw only)
# ---------------------------------------------------------------------------


def map_target_to_id(state: Mapping[str, Any], name: str | None) -> str | None:
    """Arm A's target name -> scene candidate ID (same ``scene_view`` as arm B)."""
    if not name:
        return None
    wanted = normalize_action(name)
    view = scene_view(state)
    labels: dict[str, set[str]] = {
        actor.id: {
            normalize_action(actor.id),
            normalize_action(actor.name),
            *(normalize_action(alias) for alias in actor.aliases),
        }
        for actor in view.actors
    }
    from services.entity_identity import resolve_npc_entity_id

    for key, row in (state.get("npcs") or {}).items():
        if isinstance(row, dict):
            canonical = resolve_npc_entity_id(row, key) or str(row.get("id") or "")
            if canonical in labels:
                labels[canonical].add(normalize_action(str(key)))
    for actor_id, names in labels.items():
        if wanted in names:
            return actor_id
    return None


def observations(
    raw: Mapping[str, Any], cases: Mapping[str, Case], oracle: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(eligible observations, gate observations); labels are read only here."""
    eligible, gate = [], []
    for row in raw["rows"]:
        case = cases[row["case_id"]]
        truth = case.expected
        if row["python_gate"]:
            gate.append(
                {
                    "case_id": case.id,
                    "replicate": row["replicate"],
                    "a_route": row["a"]["route"],
                    "b_route": row["b"]["route"],
                    "calls": row["a"]["calls"] + row["b"]["calls"],
                    "expected_route": truth["route"],
                }
            )
            continue
        a, b = row["a"], row["b"]
        state = case.input.get("state") or {}
        a_target = (
            map_target_to_id(state, a["target_raw"])
            if a["route"] in {"npc_actor", "combat_agent"}
            else None
        )
        a_source = a["loot_source_effective"] if a["route"] == "loot" else None
        decision = loot.frozen_loot_decision(
            route=b["answers"].get("route"),
            target=b["answers"].get("target"),
            loot_source=b["answers"].get("loot_source"),
            verbs=tuple(row["verbs"]),
            in_combat=bool(row["in_combat"]),
            target_status=row["target_status"],
        )
        covered = decision["source"] == "jev"
        eligible.append(
            {
                "case_id": case.id,
                "replicate": row["replicate"],
                "kind": case.kind,
                "critical": case.critical,
                "expected_route": truth["route"],
                "expected_target": truth.get("target"),
                "oracle_loot_source": oracle.get(case.id),
                "a_route": a["route"],
                "a_target": a_target,
                "a_target_raw": a["target_raw"],
                "a_loot_source": a_source,
                "a_latency_ms": float(a["latency_ms"]),
                "b_source": decision["source"],
                "b_reason": decision["reason"],
                "b_route": decision["route"] if covered else a["route"],
                "b_target": decision["target"] if covered else a_target,
                "b_loot_source": decision["loot_source"] if covered else a_source,
                "b_target_in_candidates": (
                    not covered
                    or decision["target"] is None
                    or decision["target"] in row["candidates"]
                ),
                "jev_latency_ms": float(b["latency_ms"]),
                "b_latency_ms": float(b["latency_ms"])
                + (0.0 if covered else float(a["latency_ms"])),
            }
        )
    return eligible, gate


def r9_1_route(obs: list[Mapping[str, Any]]) -> dict[str, Any]:
    n = len(obs)
    a_ok = sum(o["a_route"] == o["expected_route"] for o in obs)
    b_ok = sum(o["b_route"] == o["expected_route"] for o in obs)
    losses = [
        {"case_id": o["case_id"], "replicate": o["replicate"]}
        for o in obs
        if o["a_route"] == o["expected_route"] and o["b_route"] != o["expected_route"]
    ]
    wins = sum(
        o["b_route"] == o["expected_route"] and o["a_route"] != o["expected_route"] for o in obs
    )
    ok = (
        n > 0
        and Fraction(b_ok, n) >= Fraction(a_ok, n) - R9_1_MARGIN
        and len(losses) <= R9_1_MAX_PAIRED_LOSSES
    )
    return {
        "rule": "R9.1",
        "n": n,
        "a_correct": a_ok,
        "b_correct": b_ok,
        "a_accuracy": a_ok / n if n else "unavailable",
        "b_accuracy": b_ok / n if n else "unavailable",
        "paired_losses": len(losses),
        "paired_wins": wins,
        "losses": losses,
        "pass": ok,
    }


def r9_2_target(obs: list[Mapping[str, Any]]) -> dict[str, Any]:
    scope = [o for o in obs if o["kind"] == "target"]

    def ok(o: Mapping[str, Any], arm: str) -> bool:
        return (
            o[f"{arm}_route"] == o["expected_route"] and o[f"{arm}_target"] == o["expected_target"]
        )

    a_ok = sum(ok(o, "a") for o in scope)
    b_ok = sum(ok(o, "b") for o in scope)
    outside = [
        {"case_id": o["case_id"], "replicate": o["replicate"]}
        for o in obs
        if not o["b_target_in_candidates"]
    ]
    agree = sum(o["b_target"] == o["a_target"] for o in scope)
    return {
        "rule": "R9.2",
        "n": len(scope),
        "a_correct": a_ok,
        "b_correct": b_ok,
        "a_accuracy": a_ok / len(scope) if scope else "unavailable",
        "b_accuracy": b_ok / len(scope) if scope else "unavailable",
        "b_vs_a_target_agreement": agree,
        "b_targets_outside_candidates": outside,
        "pass": b_ok >= a_ok and not outside,
    }


def r9_3_unsafe(obs: list[Mapping[str, Any]]) -> dict[str, Any]:
    unsafe = [
        {"case_id": o["case_id"], "replicate": o["replicate"], "b_source": o["b_source"]}
        for o in obs
        if o["b_route"] == "combat_agent" and o["expected_route"] != "combat_agent"
    ]
    a_unsafe = sum(
        o["a_route"] == "combat_agent" and o["expected_route"] != "combat_agent" for o in obs
    )
    return {
        "rule": "R9.3",
        "b_unsafe": len(unsafe),
        "a_unsafe_informative": a_unsafe,
        "cases": unsafe,
        "pass": not unsafe,
    }


def r9_4_latency(obs: list[Mapping[str, Any]]) -> dict[str, Any]:
    a = [o["a_latency_ms"] for o in obs]
    b = [o["b_latency_ms"] for o in obs]
    a50, a95, b50, b95 = (
        percentile(a, 0.5),
        percentile(a, 0.95),
        percentile(b, 0.5),
        percentile(b, 0.95),
    )
    if "unavailable" in (a50, a95, b50, b95):
        return {"rule": "R9.4", "pass": False, "reason": "no latency"}
    gain = round(float(a50) - float(b50), 2)
    ratio = round(float(b95) / float(a95), 4) if float(a95) else float("inf")
    return {
        "rule": "R9.4",
        "a_p50_ms": a50,
        "a_p95_ms": a95,
        "b_p50_ms": b50,
        "b_p95_ms": b95,
        "p50_gain_ms": gain,
        "p95_ratio_b_over_a": ratio,
        "jev_p50_ms": percentile([o["jev_latency_ms"] for o in obs], 0.5),
        "jev_p95_ms": percentile([o["jev_latency_ms"] for o in obs], 0.95),
        "pass": gain >= R9_4_MIN_P50_GAIN_MS and float(b95) <= R9_4_MAX_P95_RATIO * float(a95),
    }


def r9_5_gates(gate_obs: list[Mapping[str, Any]]) -> dict[str, Any]:
    bad = [
        {"case_id": o["case_id"], "replicate": o["replicate"]}
        for o in gate_obs
        if o["a_route"] != o["b_route"] or o["calls"] != 0
    ]
    matches_oracle = sum(o["a_route"] == o["expected_route"] for o in gate_obs)
    return {
        "rule": "R9.5",
        "n": len(gate_obs),
        "mismatches_or_calls": bad,
        "gate_route_matches_oracle_informative": matches_oracle,
        "pass": bool(gate_obs) and not bad,
    }


def r9_6_provider(raw: Mapping[str, Any]) -> dict[str, Any]:
    errors = [entry for entry in raw.get("sanity", []) if entry.get("error")]
    for row in raw.get("rows", []):
        for arm in ("a", "b"):
            if isinstance(row.get(arm), dict) and row[arm].get("error"):
                errors.append({"case_id": row["case_id"], "arm": arm, "error": row[arm]["error"]})
    return {
        "rule": "R9.6",
        "status": raw.get("status"),
        "provider_errors": len(errors),
        "errors": errors,
        "pass": raw.get("status") == "complete" and not errors,
    }


def r9_verdict(results: Mapping[str, Mapping[str, Any]]) -> str:
    return "GO" if results and all(result["pass"] for result in results.values()) else "NO_GO"


def summarize(
    raw: Mapping[str, Any], cases: list[Case], oracle: Mapping[str, str]
) -> dict[str, Any]:
    if raw.get("status") != "complete":
        return {
            "status": raw.get("status"),
            "verdict": "no score (run not complete)",
            "r9_6": r9_6_provider(raw),
        }
    by_id = {case.id: case for case in cases}
    obs, gate_obs = observations(raw, by_id, oracle)
    results = {
        "r9_1": r9_1_route(obs),
        "r9_2": r9_2_target(obs),
        "r9_3": r9_3_unsafe(obs),
        "r9_4": r9_4_latency(obs),
        "r9_5": r9_5_gates(gate_obs),
        "r9_6": r9_6_provider(raw),
        "r9_7": loot.r9_7_loot_source(obs),
    }
    loot_obs = [o for o in obs if o["oracle_loot_source"] is not None]
    reasons: dict[str, int] = {}
    for o in obs:
        if o["b_source"] != "jev":
            reasons[o["b_reason"]] = reasons.get(o["b_reason"], 0) + 1
    calls = len(raw["sanity"]) + 2 * sum(not row["python_gate"] for row in raw["rows"])
    usage = {"classify_input_tokens": 0, "classify_output_tokens": 0}
    for row in [*raw["rows"], *raw["sanity"]]:
        for record in [row] if "arm" in row else [row.get("a"), row.get("b")]:
            if isinstance(record, dict) and isinstance(record.get("usage"), list):
                for item in record["usage"]:
                    usage["classify_input_tokens"] += item.get("input_tokens", 0)
                    usage["classify_output_tokens"] += item.get("output_tokens", 0)
    return {
        "status": "complete",
        "evidence_type": "confirmatory (FROZEN, J2, single run)",
        "run_id": raw["run_id"],
        "frozen_hash": raw["frozen_hash"],
        "frozen_oracle_hash": raw["frozen_oracle_hash"],
        "variant_id": raw["variant_id"],
        "r9_7_reference": raw["r9_7_reference"],
        "verdict": r9_verdict(results),
        "results": results,
        "coverage": {
            "covered": sum(o["b_source"] == "jev" for o in obs),
            "eligible_observations": len(obs),
            "fallback_reasons": dict(sorted(reasons.items())),
        },
        "loot_source_accuracy_informative": {
            "n": len(loot_obs),
            "a_correct": sum(o["a_loot_source"] == o["oracle_loot_source"] for o in loot_obs),
            "b_correct": sum(o["b_loot_source"] == o["oracle_loot_source"] for o in loot_obs),
            "b_jev_covered": sum(o["b_source"] == "jev" for o in loot_obs),
        },
        "calls": {
            "j2_total": calls,
            "sanity": len(raw["sanity"]),
            "reserved_usd": round(calls * hybrid.RESERVED_USD_PER_CALL, 2),
            "real_cost_usd": "unavailable",
            **usage,
        },
        "observations": obs,
        "gate_observations": gate_obs,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _gate_probe(cases: list[Case]) -> tuple[list[Case], dict[str, str]]:
    """Router probe with ``get_llm`` blocked: gates resolve with zero calls."""
    from evals.experiments.jev_router_ab import _eligible

    eligible, gates = [], {}
    for case in cases:
        reaches, route = _eligible(case)
        if reaches == case.python_gate:
            raise CorpusError(f"python_gate flag disagrees with the router probe: {case.id}")
        if reaches:
            eligible.append(case)
        else:
            gates[case.id] = str(route)
    return eligible, gates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("run", "summarize"), required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--owner-rerun-authorization", default=None)
    args = parser.parse_args()
    if args.phase == "summarize":
        cases, _ = load_frozen_cases()
        oracle, _ = load_frozen_oracle()
        raw = json.loads((args.run_dir / "raw.json").read_text(encoding="utf-8"))
        _write_json(args.run_dir / "summary.json", summarize(raw, cases, oracle))
        print(
            json.dumps(
                {
                    "raw_sha256": sha256_file(args.run_dir / "raw.json"),
                    "summary_sha256": sha256_file(args.run_dir / "summary.json"),
                }
            )
        )
        return
    from dotenv import load_dotenv

    from evals.experiments.jev_router_hybrid import load_dev_cases
    from services.jev_decision import JevDecisionBackend

    if args.env_file:
        load_dotenv(args.env_file, override=False)
    for flag in ("RPG_FORCE_MOCK", "RPG_NO_MOCK", "LLM_PROVIDER", "RPG_ROUTES"):
        if os.getenv(flag):
            raise SystemExit(f"{flag} invalidates the current CLASSIFY cascade")
    if (os.getenv("RPG_JEV_ROUTER_MODE") or "off").strip().lower() != "off":
        raise SystemExit("RPG_JEV_ROUTER_MODE must be off for arm A")
    if os.getenv("TYPESAFE_API_KEY") is None and os.getenv("JEVMODEL_API_KEY") is None:
        raise SystemExit("TypeSafe key not configured")
    structure = verify_frozen_structure()
    cases, frozen_hash = load_frozen_cases()
    oracle, oracle_hash = load_frozen_oracle()
    dev_cases, _ = load_dev_cases()
    sanity_outside_corpora(SANITY_CASE, cases, dev_cases)
    eligible, gates = _gate_probe(cases)
    if not _gate_probe([SANITY_CASE])[0]:
        raise SystemExit("sanity case does not reach CLASSIFY")
    if set(oracle) - {case.id for case in eligible}:
        raise SystemExit("oracle ids are not eligible FROZEN cases")
    sha, tree, dirty = repository_identity(ROOT)
    if dirty:
        raise SystemExit("product tree is dirty; commit the runner before the live run")
    ledger = J2Ledger()
    needed = required_calls(len(eligible))
    if ledger.remaining() < needed:
        raise SystemExit(f"{needed} calls needed, {ledger.remaining()} remain in the J2 cap")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"SPEC-217-J2-{stamp}"
    claim_single_run(MARKER, ledger, run_id, args.owner_rerun_authorization)
    meta = {
        "run_id": run_id,
        "spec": "SPEC-217",
        "spec_loot": "SPEC-238",
        "product_sha": sha,
        "product_tree_hash": tree,
        "product_dirty": dirty,
        "frozen_hash": frozen_hash,
        "frozen_oracle_hash": oracle_hash,
        "r9_7_reference": R9_7_REFERENCE,
        **structure,
        "required_calls": needed,
        "ledger_before": {k: v for k, v in ledger.read().items() if k != "entries"},
    }
    with JevDecisionBackend(
        max_retries=0, timeout_seconds=8.0, total_timeout_seconds=10.0
    ) as backend:
        raw = run_j2(
            eligible=eligible,
            gates=gates,
            sanity=SANITY_CASE,
            classify=live_classify(ledger),
            jev=jev_call(backend, ledger, run_id),
            ledger=ledger,
            output_dir=RUNS / stamp,
            meta=meta,
        )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "status": raw["status"],
                "dir": str(RUNS / stamp),
                "ledger": raw["ledger_after"],
            }
        )
    )


if __name__ == "__main__":
    main()
