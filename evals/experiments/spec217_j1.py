"""SPEC-217 J1 live runner (DEV corpus only; Jev only, zero CLASSIFY calls).

P1 (screening): one Jev call per eligible DEV case carrying every route label
set plus the target stage on one enriched state. P2 (structure check): the
exact frozen-candidate request on the DEV ``critical`` cases. A disk ledger
caps J1 at 60 external calls (spec total 160) across restarts; any provider
error stops the run without a score. The FROZEN corpus is never opened.

Run: ``uv run python -m evals.experiments.spec217_j1 --phase p1 --env-file <.env>``.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from dotenv import load_dotenv

from evals.core.hashing import repository_identity, sha256_file
from evals.experiments.jev_router_ab import _eligible, _write_json
from evals.experiments.jev_router_hybrid import (
    J1_CALL_CAP, ROOT, RESERVED_USD_PER_CALL, TOTAL_CALL_CAP, Case, Policy,
    digest_of, frozen_lock_digest, frozen_request, load_dev_cases, scene_view,
    screening_request, extract_verbs, summarize,
)
from services.jev_decision import (
    ChoiceAnswer, DecisionBackend, DecisionRequest, JevDecisionBackend, JevError,
)


RUNS = ROOT / "evals/runs/jev-router-ab/spec217-j1"
LEDGER = RUNS / "ledger.json"


class BudgetExhausted(RuntimeError):
    pass


class CallLedger:
    """Durable external-call counter; increments *before* any network I/O."""

    def __init__(self, path: Path = LEDGER, j1_cap: int = J1_CALL_CAP,
                 total_cap: int = TOTAL_CALL_CAP) -> None:
        self.path, self.j1_cap, self.total_cap = path, j1_cap, total_cap

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"spec": "SPEC-217", "j1_calls": 0, "total_calls": 0,
                    "reserved_usd_per_call": RESERVED_USD_PER_CALL, "entries": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def remaining(self) -> int:
        data = self.read()
        return max(0, min(self.j1_cap - data["j1_calls"], self.total_cap - data["total_calls"]))

    def consume(self, phase: str, case_id: str, provider: str = "jev") -> int:
        data = self.read()
        if data["j1_calls"] >= self.j1_cap or data["total_calls"] >= self.total_cap:
            raise BudgetExhausted("SPEC-217 J1 external call cap reached")
        data["j1_calls"] += 1
        data["total_calls"] += 1
        data["entries"].append({
            "n": data["total_calls"], "phase": phase, "case_id": case_id, "provider": provider,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        data["reserved_usd"] = round(data["total_calls"] * RESERVED_USD_PER_CALL, 2)
        _write_json(self.path, data)
        return data["total_calls"]


def _answers(result_answers: Mapping[str, Any]) -> dict[str, Any]:
    out = {}
    for name, answer in result_answers.items():
        if not isinstance(answer, ChoiceAnswer):
            raise JevError(f"non-choice answer for {name}")
        out[name] = {"choice": answer.choice, "confidence": answer.confidence,
                     "probabilities": dict(answer.probabilities)}
    return out


def _row(case: Case, request: DecisionRequest) -> dict[str, Any]:
    state = case.input.get("state") or {}
    view = scene_view(state)
    return {
        "case_id": case.id, "kind": case.kind,
        "verbs": list(extract_verbs(str(case.input.get("action") or ""))),
        "in_combat": bool((state.get("combat") or {}).get("active")),
        "target_status": view.target_status,
        "unrepresentable_reason": view.unrepresentable_reason,
        "questions": sorted(request.questions),
        "request_digest": digest_of(request.wire_body()),
    }


def run_phase(
    phase: str, cases: list[Case], build: Callable[[Case], DecisionRequest],
    backend: DecisionBackend, ledger: CallLedger, output_dir: Path,
    meta: Mapping[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    raw_path = output_dir / "raw.json"
    raw: dict[str, Any] = {**meta, "phase": phase, "status": "in_progress",
                           "started_at": datetime.now(timezone.utc).isoformat(),
                           phase: {"rows": []}}
    _write_json(raw_path, raw)
    try:
        for case in cases:
            request = build(case)
            row = _row(case, request)
            raw[phase]["rows"].append(row)
            row["call_n"] = ledger.consume(phase, case.id)
            start = time.perf_counter()
            key = f"spec217-j1-{phase}-{meta['run_id']}-{row['call_n']}"
            try:
                result = backend.decide(request, idempotency_key=key)
            except JevError as exc:
                row["error"] = getattr(exc, "code", "jev_error")
                raise
            row.update({
                "answers": _answers(result.answers),
                "latency_ms": round((time.perf_counter() - start) * 1000),
                "provider_latency_ms": result.latency_ms, "model": result.model,
                "usage": result.usage.model_dump() if result.usage else "unavailable",
                "cost_usd": result.cost_usd if result.cost_usd is not None else "unavailable",
                "error": None,
            })
            _write_json(raw_path, raw)
        raw["status"] = "complete"
    except BudgetExhausted as exc:
        raw["status"] = "stopped-budget"
        raw["blocker"] = str(exc)
    except JevError as exc:
        raw["status"] = "blocked-by-provider"
        raw["blocker"] = f"{type(exc).__name__}: {getattr(exc, 'code', 'jev_error')}"
    finally:
        raw["finished_at"] = datetime.now(timezone.utc).isoformat()
        raw["ledger_after"] = {k: v for k, v in ledger.read().items() if k != "entries"}
        _write_json(raw_path, raw)
    return raw


def _meta(cases_digest: str, run_id: str) -> dict[str, Any]:
    sha, tree, dirty = repository_identity(ROOT)
    return {"run_id": run_id, "spec": "SPEC-217", "stage": "J1",
            "product_sha": sha, "product_tree_hash": tree, "product_dirty": dirty,
            "dev_hash": cases_digest, "frozen_lock_hash_only": frozen_lock_digest()}


def eligible_cases(cases: list[Case]) -> list[Case]:
    rows = []
    for case in cases:
        is_eligible, _route = _eligible(case)
        if is_eligible == case.python_gate:
            raise RuntimeError(f"python_gate flag disagrees with the router probe: {case.id}")
        if is_eligible:
            rows.append(case)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("p1", "p2", "summarize"), required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--p1-dir", type=Path, help="P1 run directory (p2/summarize)")
    args = parser.parse_args()
    cases, digest = load_dev_cases()
    if args.phase == "summarize":
        raw = json.loads((args.p1_dir / "raw.json").read_text(encoding="utf-8"))
        if raw["status"] != "complete":
            raise SystemExit("P1 raw is not complete; no score")
        _write_json(args.p1_dir / "summary.json", summarize(raw, cases))
        print(json.dumps({"summary": str(args.p1_dir / "summary.json"),
                          "raw_sha256": sha256_file(args.p1_dir / "raw.json"),
                          "summary_sha256": sha256_file(args.p1_dir / "summary.json")}))
        return
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    if os.getenv("TYPESAFE_API_KEY") is None and os.getenv("JEVMODEL_API_KEY") is None:
        raise SystemExit("TypeSafe key not configured")
    eligible = eligible_cases(cases)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"SPEC-217-J1-{args.phase}-{stamp}"
    ledger = CallLedger()
    if args.phase == "p1":
        targets = eligible
        build: Callable[[Case], DecisionRequest] = lambda case: screening_request(case.input)
        extra: dict[str, Any] = {}
    else:
        summary = json.loads((args.p1_dir / "summary.json").read_text(encoding="utf-8"))
        policy = Policy(**summary["chosen"]["policy"])
        targets = [case for case in eligible if case.critical]
        build = lambda case: frozen_request(case.input, policy)
        extra = {"policy": asdict(policy), "variant_id": policy.variant_id,
                 "p1_summary_sha256": sha256_file(args.p1_dir / "summary.json")}
    if len(targets) > ledger.remaining():
        raise SystemExit(f"{len(targets)} calls needed, {ledger.remaining()} remain in the J1 cap")
    with JevDecisionBackend(max_retries=0, timeout_seconds=8.0, total_timeout_seconds=10.0) as backend:
        raw = run_phase(args.phase, targets, build, backend, ledger, RUNS / stamp,
                        {**_meta(digest, run_id), **extra})
    print(json.dumps({"run_id": run_id, "status": raw["status"], "dir": str(RUNS / stamp),
                      "ledger": raw["ledger_after"]}))


if __name__ == "__main__":
    main()
