"""SPEC-238 J1b: loot-source stage on top of the SPEC-217 J1 frozen structure.

When the Jev routes ``loot`` it also decides the loot source
(``TREASURE``/``SHOP``/``CRAFT`` — the router's ``loot_source`` contract,
``agents/router.py``) in the *same* request, so a covered loot case costs no
extra call. Low confidence, abstention or a Python consistency guard send the
case to CLASSIFY, exactly like the J1 policy. The J1 frozen code in
``jev_router_hybrid.py`` is reused untouched (its Astra-approved digest stays
valid); this module only wraps it. Production is unchanged
(``RPG_JEV_ROUTER_MODE`` default ``off``). The FROZEN corpus is never opened.

Live run (DEV only):
``uv run python -m evals.experiments.spec238_loot --phase run --env-file <.env>``.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
from typing import Any, Mapping

from evals.core.hashing import sha256_file
from evals.experiments import jev_router_hybrid as hybrid
from evals.experiments.jev_router_ab import _write_json
from evals.experiments.jev_router_hybrid import (
    DEFAULT_TAU, FROZEN_J1_POLICY, ROOT, TAU_GRID, Case, Policy, digest_of,
    frozen_request, hybrid_decision, percentile,
)
from gamedata import get_location
from services.economy import merchants_at
from services.jev_decision import ChoiceQuestion, DecisionRequest


ORACLE = ROOT / "evals/experiments/data/spec238_loot_oracle.json"
ORACLE_SHA256 = "sha256:129ac6fb9ff0c298c9b594d8db3afd756358063d4b7c5cbafe30d359fae00493"
RUNS = ROOT / "evals/runs/jev-router-ab/spec238-j1b"
J1B_CALL_CAP = 30
TOTAL_CALL_CAP = 190  # SPEC-217 total raised 160 -> 190 by the owner (2026-10-18)
NON_LOOT_SAMPLE = 9   # + 8 DEV critical + 13 DEV loot = 30 calls
SAMPLE_SEED = "SPEC-238-J1b"
LOOT_SOURCES = ("TREASURE", "SHOP", "CRAFT")


# ---------------------------------------------------------------------------
# Deterministic public features
# ---------------------------------------------------------------------------

def loot_features(state: Mapping[str, Any]) -> dict[str, bool | None]:
    """Location facts from public catalogs only; ``None`` when the location is unknown."""
    world = (state or {}).get("world") or {}
    location_id = str(world.get("current_location_id") or "")
    node = get_location(location_id) if location_id else {}
    if not node:
        return {"merchant_here": None, "craft_station": None}
    return {"merchant_here": bool(merchants_at(location_id)),
            "craft_station": bool(node.get("craft_tags"))}


LOOT_SOURCE_INSTRUCTIONS = (
    "Se state.action envolver itens, de onde eles vêm? Escolha exatamente uma chave. "
    "state.verbs traz sinais de verbo extraídos por código; state.merchant_here indica "
    "um mercador no local; state.craft_station indica uma oficina no local."
)
LOOT_SOURCE_QUESTION = ChoiceQuestion(
    instructions=LOOT_SOURCE_INSTRUCTIONS,
    criteria={
        "treasure": "Achado: pegar, apanhar, vasculhar, saquear um corpo ou abrir um baú",
        "shop": "Comércio: comprar, vender, trocar ou pagar a um mercador",
        "craft": "Fabricação: forjar, fabricar, construir ou criar um item",
        "none": "A ação não envolve pegar, negociar ou fabricar itens",
    },
)


def j1b_request(case_input: Mapping[str, Any], base: Policy = FROZEN_J1_POLICY) -> DecisionRequest:
    """J1 frozen request + loot features + a loot_source question (one call)."""
    request = frozen_request(case_input, base)
    features = loot_features(case_input.get("state") or {})
    state = request.state.model_copy(update=features)
    return DecisionRequest(state=state, questions={**request.questions,
                                                   "loot_source": LOOT_SOURCE_QUESTION})


# ---------------------------------------------------------------------------
# Policy (pure)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LootPolicy:
    base: Policy = field(default_factory=lambda: FROZEN_J1_POLICY)
    loot_stage: bool = True
    loot_guard: bool = True
    loot_tau: float = DEFAULT_TAU

    @property
    def variant_id(self) -> str:
        if not self.loot_stage:
            return self.base.variant_id
        return (f"{self.base.variant_id}+lootsrc{'+lguard' if self.loot_guard else ''}"
                f"@{self.loot_tau:.2f}")


def loot_guard_ok(source: str, verbs: tuple[str, ...], merchant_here: bool | None,
                  craft_station: bool | None) -> bool:
    """Python consistency check between the Jev source and public signals."""
    if not {"take", "trade", "craft"} & set(verbs):
        return False  # no item verb at all: a loot route is not trusted
    if source == "SHOP":
        return "trade" in verbs or merchant_here is True
    if source == "CRAFT":
        return "craft" in verbs or craft_station is True
    return "trade" not in verbs and "craft" not in verbs  # TREASURE


def loot_hybrid_decision(
    *, route: Mapping[str, Any] | None, target: Mapping[str, Any] | None,
    loot_source: Mapping[str, Any] | None, verbs: tuple[str, ...], in_combat: bool,
    target_status: str, merchant_here: bool | None, craft_station: bool | None,
    policy: LootPolicy,
) -> dict[str, Any]:
    """J1 frozen decision; when it defers loot by scope, try the loot-source stage."""
    decision = hybrid_decision(route=route, target=target, verbs=verbs, in_combat=in_combat,
                               target_status=target_status, policy=policy.base)
    decision = {**decision, "loot_source": None}
    if decision["reason"] != "loot_context_out_of_scope" or not policy.loot_stage:
        return decision

    def fallback(reason: str) -> dict[str, Any]:
        return {"source": "fallback", "reason": reason, "route": None, "target": None,
                "loot_source": None}

    if loot_source is None:
        return fallback("loot_source_missing")
    if loot_source["choice"] == "none":
        return fallback("loot_source_abstain")
    if float(loot_source["confidence"]) < policy.loot_tau:
        return fallback("loot_source_low_confidence")
    source = str(loot_source["choice"]).upper()
    if source not in LOOT_SOURCES:
        return fallback("loot_source_invalid")
    if policy.loot_guard and not loot_guard_ok(source, verbs, merchant_here, craft_station):
        return fallback("loot_guard")
    return {"source": "jev", "reason": None, "route": "loot", "target": None,
            "loot_source": source}


# ---------------------------------------------------------------------------
# Sample, oracle, scoring (offline, from raw only)
# ---------------------------------------------------------------------------

def load_oracle(path: Path = ORACLE) -> dict[str, str]:
    if sha256_file(path) != ORACLE_SHA256:
        raise hybrid.CorpusError("SPEC-238 loot oracle hash mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {case_id: row["loot_source"] for case_id, row in data["labels"].items()}


def _rank(case_id: str) -> str:
    return hashlib.sha256(f"{SAMPLE_SEED}|{case_id}".encode("utf-8")).hexdigest()


def j1b_sample(eligible: list[Case]) -> list[Case]:
    """All DEV loot + all DEV critical + 9 other non-loot by seeded hash order."""
    loot = [case for case in eligible if case.expected["route"] == "loot"]
    critical = [case for case in eligible if case.critical and case not in loot]
    rest = sorted((case for case in eligible if case not in loot and case not in critical),
                  key=lambda case: _rank(case.id))
    return loot + critical + rest[:NON_LOOT_SAMPLE]


def candidate_policies() -> list[LootPolicy]:
    return [LootPolicy(loot_guard=guard, loot_tau=tau) for guard in (True, False) for tau in TAU_GRID]


def score(rows: list[Mapping[str, Any]], cases: Mapping[str, Case], oracle: Mapping[str, str],
          policy: LootPolicy) -> dict[str, Any]:
    covered = route_errors = target_errors = source_errors = unsafe = 0
    loot_cases = loot_covered = 0
    reasons: dict[str, int] = {}
    misses: list[dict[str, Any]] = []
    for row in rows:
        case = cases[row["case_id"]]
        truth = case.expected
        answers = row["answers"]
        features = loot_features(case.input.get("state") or {})
        decision = loot_hybrid_decision(
            route=answers.get("route"), target=answers.get("target"),
            loot_source=answers.get("loot_source"), verbs=tuple(row["verbs"]),
            in_combat=bool(row["in_combat"]), target_status=row["target_status"],
            policy=policy, **features,
        )
        is_loot = truth["route"] == "loot"
        loot_cases += is_loot
        if decision["source"] != "jev":
            reasons[decision["reason"]] = reasons.get(decision["reason"], 0) + 1
            continue
        covered += 1
        route_ok = decision["route"] == truth["route"]
        target_ok = case.kind != "target" or (route_ok and decision["target"] == truth.get("target"))
        source_ok = decision["route"] != "loot" or (is_loot and decision["loot_source"] == oracle.get(case.id))
        route_errors += not route_ok
        target_errors += not target_ok
        source_errors += decision["route"] == "loot" and not source_ok
        unsafe += decision["route"] == "combat_agent" and truth["route"] != "combat_agent"
        loot_covered += is_loot and route_ok
        if not (route_ok and target_ok and source_ok):
            misses.append({"case_id": case.id, "expected": {**truth, "loot_source": oracle.get(case.id)},
                           "jev": {k: decision[k] for k in ("route", "target", "loot_source")}})
    total = len(rows)
    return {
        "variant_id": policy.variant_id, "policy": {**asdict(policy), "base": asdict(policy.base)},
        "rows": total, "covered": covered, "coverage": covered / total if total else "unavailable",
        "loot_cases": loot_cases, "loot_covered": loot_covered,
        "covered_route_errors": route_errors, "covered_target_errors": target_errors,
        "covered_loot_source_errors": source_errors, "unsafe_combat_escalations": unsafe,
        "fallback_reasons": dict(sorted(reasons.items())), "misses": misses,
    }


def adoptable(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    """Pre-registered (docs/spec217/j1b-loot.md, committed before any live call)."""
    return (candidate["covered_loot_source_errors"] == 0 and candidate["covered_route_errors"] == 0
            and candidate["covered_target_errors"] == 0
            and candidate["unsafe_combat_escalations"] == 0
            and candidate["covered"] > baseline["covered"])


def select(scores: list[Mapping[str, Any]], baseline: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Max coverage among adoptable; ties → guard on → loot τ nearest 0.50."""
    pool = [s for s in scores if adoptable(s, baseline)]
    if not pool:
        return None
    return sorted(pool, key=lambda s: (-s["covered"], not s["policy"]["loot_guard"],
                                       abs(s["policy"]["loot_tau"] - DEFAULT_TAU)))[0]


def summarize(raw: Mapping[str, Any], cases: list[Case], oracle: Mapping[str, str]) -> dict[str, Any]:
    by_id = {case.id: case for case in cases}
    rows = [row for row in raw["j1b"]["rows"] if row.get("answers")]
    baseline = score(rows, by_id, oracle, LootPolicy(loot_stage=False))
    scores = [score(rows, by_id, oracle, policy) for policy in candidate_policies()]
    chosen = select(scores, baseline)
    non_loot = [row for row in rows if by_id[row["case_id"]].expected["route"] != "loot"]
    latency = [float(row["latency_ms"]) for row in rows]
    return {
        "evidence_type": "development (DEV corpus, SPEC-238 J1b)", "promotion": False,
        "dev_hash": raw["dev_hash"], "oracle_hash": raw["oracle_hash"], "rows": len(rows),
        "selection_rule": "adopt iff 0 covered loot-source errors, 0 covered route/target "
                          "errors, 0 unsafe, coverage > baseline; max coverage; ties guard "
                          "on, loot τ nearest 0.50",
        "baseline": {k: v for k, v in baseline.items() if k != "misses"},
        "baseline_misses": baseline["misses"],
        "chosen": chosen, "adopted": chosen is not None,
        "non_loot_route_answers": {row["case_id"]: row["answers"]["route"]["choice"] for row in non_loot},
        "jev_latency_ms_p50": percentile(latency, 0.5),
        "jev_latency_ms_p95": percentile(latency, 0.95),
        "variants": [{k: v for k, v in s.items() if k != "misses"} for s in scores],
    }


# ---------------------------------------------------------------------------
# Freeze (filled after the J1b decision)
# ---------------------------------------------------------------------------

def structure_digest(policy: LootPolicy) -> str:
    """J1 frozen digest + everything the loot stage sends or decides with."""
    return digest_of({
        "j1_structure_digest": hybrid.structure_digest(policy.base),
        "policy": {**asdict(policy), "base": asdict(policy.base)},
        "loot_source_question": LOOT_SOURCE_QUESTION.model_dump(),
        "decision_code": {fn.__name__: inspect.getsource(fn).replace("\r\n", "\n")
                          for fn in (loot_features, j1b_request, loot_guard_ok,
                                     loot_hybrid_decision, merchants_at)},
    })


# ---------------------------------------------------------------------------
# Ledger + live runner (DEV only)
# ---------------------------------------------------------------------------

class J1bLedger:
    """Shared SPEC-217 ledger; J1b counter capped at 30, spec total at 190."""

    def __init__(self, path: Path | None = None, j1b_cap: int = J1B_CALL_CAP,
                 total_cap: int = TOTAL_CALL_CAP) -> None:
        from evals.experiments.spec217_j1 import LEDGER
        self.path, self.j1b_cap, self.total_cap = path or LEDGER, j1b_cap, total_cap

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"spec": "SPEC-217", "j1_calls": 0, "total_calls": 0, "entries": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def remaining(self) -> int:
        data = self.read()
        return max(0, min(self.j1b_cap - data.get("j1b_calls", 0),
                          self.total_cap - data["total_calls"]))

    def consume(self, phase: str, case_id: str, provider: str = "jev") -> int:
        from evals.experiments.spec217_j1 import BudgetExhausted
        data = self.read()
        if data.get("j1b_calls", 0) >= self.j1b_cap or data["total_calls"] >= self.total_cap:
            raise BudgetExhausted("SPEC-238 J1b external call cap reached")
        data["j1b_calls"] = data.get("j1b_calls", 0) + 1
        data["total_calls"] += 1
        data["total_cap"] = self.total_cap
        data["entries"].append({"n": data["total_calls"], "phase": phase, "case_id": case_id,
                                "provider": provider, "at": datetime.now(timezone.utc).isoformat()})
        data["reserved_usd"] = round(data["total_calls"] * hybrid.RESERVED_USD_PER_CALL, 2)
        _write_json(self.path, data)
        return data["total_calls"]


def main() -> None:
    from dotenv import load_dotenv
    from evals.experiments.spec217_j1 import _meta, eligible_cases, run_phase
    from services.jev_decision import JevDecisionBackend

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("run", "summarize"), required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    cases, digest = hybrid.load_dev_cases()
    oracle = load_oracle()
    if args.phase == "summarize":
        raw = json.loads((args.run_dir / "raw.json").read_text(encoding="utf-8"))
        if raw["status"] != "complete":
            raise SystemExit("J1b raw is not complete; no score")
        _write_json(args.run_dir / "summary.json", summarize(raw, cases, oracle))
        print(json.dumps({"raw_sha256": sha256_file(args.run_dir / "raw.json"),
                          "summary_sha256": sha256_file(args.run_dir / "summary.json")}))
        return
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    if os.getenv("TYPESAFE_API_KEY") is None and os.getenv("JEVMODEL_API_KEY") is None:
        raise SystemExit("TypeSafe key not configured")
    sample = j1b_sample(eligible_cases(cases))
    ledger = J1bLedger()
    if len(sample) > ledger.remaining():
        raise SystemExit(f"{len(sample)} calls needed, {ledger.remaining()} remain in the J1b cap")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"SPEC-238-J1b-{stamp}"
    meta = {**_meta(digest, run_id), "stage": "J1b", "spec_j1b": "SPEC-238",
            "oracle_hash": ORACLE_SHA256, "base_variant": FROZEN_J1_POLICY.variant_id,
            "j1_structure_digest": hybrid.FROZEN_J1_STRUCTURE_DIGEST,
            "sample": [case.id for case in sample]}
    with JevDecisionBackend(max_retries=0, timeout_seconds=8.0, total_timeout_seconds=10.0) as backend:
        raw = run_phase("j1b", sample, lambda case: j1b_request(case.input), backend, ledger,
                        RUNS / stamp, meta)
    print(json.dumps({"run_id": run_id, "status": raw["status"], "dir": str(RUNS / stamp),
                      "ledger": raw["ledger_after"]}))


if __name__ == "__main__":
    main()
