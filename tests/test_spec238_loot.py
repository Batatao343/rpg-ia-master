"""SPEC-238 J1b: Jev loot-source stage — offline, no provider traffic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.experiments import jev_router_hybrid as hybrid
from evals.experiments import spec238_loot as loot
from evals.experiments.spec217_j1 import BudgetExhausted, eligible_cases, run_phase
from evals.experiments.spec238_loot import (
    LootPolicy,
    j1b_request,
    j1b_sample,
    load_oracle,
    loot_features,
    loot_guard_ok,
    loot_hybrid_decision,
)
from services.jev_decision import ChoiceAnswer, DecisionResult, DecisionState
from services.jev_rollout import frozen_request as rollout_request


def _ans(choice: str, confidence: float = 0.9) -> dict:
    return {"choice": choice, "confidence": confidence}


def _decide(route="loot", source="shop", conf=0.9, verbs=("trade",), policy=None, **kw):
    return loot_hybrid_decision(
        route=_ans(route),
        target=None,
        loot_source=None if source is None else _ans(source, conf),
        verbs=verbs,
        in_combat=False,
        target_status="no_candidates",
        merchant_here=kw.get("merchant_here"),
        craft_station=kw.get("craft_station"),
        policy=policy or LootPolicy(),
    )


def test_loot_stage_covers_confident_consistent_loot() -> None:
    decision = _decide()
    assert decision == {
        "source": "jev",
        "reason": None,
        "route": "loot",
        "target": None,
        "loot_source": "SHOP",
    }
    assert _decide(source="craft", verbs=("craft",))["loot_source"] == "CRAFT"
    assert _decide(source="treasure", verbs=("take",))["loot_source"] == "TREASURE"


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"source": None}, "loot_source_missing"),
        ({"source": "none"}, "loot_source_abstain"),
        ({"conf": 0.49}, "loot_source_low_confidence"),
        ({"source": "craft"}, "loot_guard"),  # craft without craft verb/station
        ({"source": "treasure"}, "loot_guard"),  # treasure with a trade verb
        ({"source": "shop", "verbs": ("take",)}, "loot_guard"),  # shop with no trade verb/merchant
        ({"source": "treasure", "verbs": ()}, "loot_guard"),  # no item verb at all
        ({"source": "treasure", "verbs": ("observe",)}, "loot_guard"),
    ],
)
def test_loot_stage_falls_back_to_classify(kwargs, reason) -> None:
    decision = _decide(**kwargs)
    assert decision["source"] == "fallback" and decision["reason"] == reason
    assert decision["loot_source"] is None


def test_public_location_signals_can_satisfy_the_guard() -> None:
    assert loot_guard_ok("SHOP", ("take",), True, None)
    assert loot_guard_ok("CRAFT", ("take",), None, True)
    assert not loot_guard_ok("SHOP", ("take",), False, None)


def test_without_loot_stage_policy_is_the_j1_frozen_one() -> None:
    off = LootPolicy(loot_stage=False)
    assert off.variant_id == hybrid.FROZEN_J1_POLICY.variant_id
    assert _decide(policy=off)["reason"] == "loot_context_out_of_scope"
    assert LootPolicy().variant_id == "plain+target+guard@0.50+lootsrc+lguard@0.50"


def test_non_loot_routes_are_decided_by_j1_policy_unchanged() -> None:
    """The stage only touches the J1 'loot out of scope' fallback; others pass through."""
    for verbs, route in ((("talk",), "npc_actor"), (("move",), "storyteller")):
        decision = loot_hybrid_decision(
            route=_ans(route),
            target=_ans("none"),
            loot_source=_ans("shop"),
            verbs=verbs,
            in_combat=False,
            target_status="no_candidates",
            merchant_here=True,
            craft_station=True,
            policy=LootPolicy(),
        )
        base = hybrid.hybrid_decision(
            route=_ans(route),
            target=_ans("none"),
            verbs=verbs,
            in_combat=False,
            target_status="no_candidates",
            policy=hybrid.FROZEN_J1_POLICY,
        )
        assert {k: decision[k] for k in base} == base and decision["loot_source"] is None
    guarded = loot_hybrid_decision(
        route=_ans("combat_agent"),
        target=_ans("npc_x"),
        loot_source=_ans("shop"),
        verbs=("talk",),
        in_combat=False,
        target_status="ok",
        merchant_here=None,
        craft_station=None,
        policy=LootPolicy(),
    )
    assert guarded["reason"] == "combat_guard"


def test_loot_features_are_public_and_bounded() -> None:
    assert loot_features({}) == {"merchant_here": None, "craft_station": None}
    assert loot_features({"world": {"current_location_id": "skallgard"}})["merchant_here"] is True
    assert loot_features({"world": {"current_location_id": "nova_arcadia"}}) == {
        "merchant_here": False,
        "craft_station": False,
    }
    assert loot_features({"world": {"current_location_id": "na_anel_dourado"}}) == {
        "merchant_here": True,
        "craft_station": True,
    }
    request = j1b_request(
        {"action": "Compro uma poção", "state": {"world": {"current_location_id": "skallgard"}}}
    )
    assert set(request.questions) == {"route", "loot_source"}
    body = request.wire_body()
    assert body["state"]["merchant_here"] is True and set(
        body["questions"]["loot_source"]["criteria"]
    ) == {"treasure", "shop", "craft", "none"}
    unknown = j1b_request({"action": "Compro uma poção", "state": {}}).wire_body()["state"]
    assert "merchant_here" not in unknown and "craft_station" not in unknown
    with pytest.raises(ValueError):
        DecisionState(action="x", merchant_here="sim")


def test_j1b_request_keeps_the_j1_route_and_target_questions() -> None:
    case_input = {
        "action": "Falo com Corvo",
        "state": {
            "npcs": {
                "Corvo": {
                    "id": "npc_corvo_rapido",
                    "name": "Corvo",
                    "in_scene": True,
                    "known_by_player": True,
                }
            }
        },
    }
    j1 = hybrid.frozen_request(case_input, hybrid.FROZEN_J1_POLICY).wire_body()
    j1b = j1b_request(case_input).wire_body()
    assert j1b["questions"]["route"] == j1["questions"]["route"]
    assert j1b["questions"]["target"] == j1["questions"]["target"]
    assert j1b["state"] == j1["state"]  # unknown location: no loot features on the wire


def test_production_rollout_payload_is_frozen_without_location() -> None:
    # SPEC-217 R14: production sends the J2 request; location features stay off.
    body = rollout_request({"world": {"current_location_id": "brekmar"}}, "compro").wire_body()
    assert "loot_source" in body["questions"]
    assert "merchant_here" not in body["state"] and "craft_station" not in body["state"]


def test_oracle_matches_its_sources_and_covers_every_dev_loot_case() -> None:
    oracle = load_oracle()
    cases, _ = hybrid.load_dev_cases()
    loot_ids = {c.id for c in cases if c.expected["route"] == "loot"}
    assert set(oracle) == loot_ids and len(loot_ids) == 13
    data = json.loads(loot.ORACLE.read_text(encoding="utf-8"))["labels"]
    sources = {}
    for name in (
        "evals/datasets/regression/routing_actions.jsonl",
        "evals/experiments/data/spec179_corpus.jsonl",
    ):
        for line in (hybrid.ROOT / name).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                sources[f"{name}#{row['id']}"] = row["expected"].get("loot_context")
    for case_id, row in data.items():
        if row["provenance"] in sources:
            assert sources[row["provenance"]] == row["loot_source"], case_id


def test_oracle_hash_mismatch_aborts(tmp_path: Path) -> None:
    bad = tmp_path / "oracle.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(hybrid.CorpusError):
        load_oracle(bad)


def test_sample_is_deterministic_and_fits_the_cap() -> None:
    cases, _ = hybrid.load_dev_cases()
    eligible = eligible_cases(cases)
    sample = j1b_sample(eligible)
    assert len(sample) == 30 == loot.J1B_CALL_CAP
    assert sum(c.expected["route"] == "loot" for c in sample) == 13
    assert sum(bool(c.critical) for c in sample) == 8
    assert len({c.id for c in sample}) == 30
    assert [c.id for c in sample] == [c.id for c in j1b_sample(eligible)]


def test_ledger_caps_j1b_30_and_total_190(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(
        json.dumps({"spec": "SPEC-217", "j1_calls": 60, "total_calls": 60, "entries": []}),
        encoding="utf-8",
    )
    ledger = loot.J1bLedger(path)
    assert ledger.remaining() == 30
    for index in range(30):
        ledger.consume("j1b", f"c{index}")
    with pytest.raises(BudgetExhausted):
        loot.J1bLedger(path).consume("j1b", "late")  # survives restart
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_calls"] == 90 and data["j1b_calls"] == 30 and data["j1_calls"] == 60
    total = tmp_path / "t.json"
    total.write_text(
        json.dumps({"j1_calls": 60, "total_calls": 185, "entries": []}), encoding="utf-8"
    )
    capped = loot.J1bLedger(total)
    assert capped.remaining() == 5
    for index in range(5):
        capped.consume("j1b", str(index))
    with pytest.raises(BudgetExhausted):
        capped.consume("j1b", "x")


class _Backend:
    """Answers the oracle-shaped first option, or a fixed map per question."""

    def __init__(self, fail_at: int | None = None, picks: dict | None = None) -> None:
        self.calls, self.fail_at, self.picks = 0, fail_at, picks or {}

    def decide(self, request, *, idempotency_key=None, correlation_id=None):
        from services.jev_decision import JevRateLimitError

        self.calls += 1
        if self.calls == self.fail_at:
            raise JevRateLimitError("Jev HTTP 429")
        answers = {}
        for name, question in request.questions.items():
            keys = list(question.criteria)
            choice = self.picks.get(name, keys[0])
            probabilities = {key: (0.9 if key == choice else 0.1 / (len(keys) - 1)) for key in keys}
            answers[name] = ChoiceAnswer(
                type="choice", choice=choice, probabilities=probabilities, confidence=0.9
            )
        return DecisionResult(
            model="jev-test", answers=answers, usage=None, correlation_id="c", latency_ms=5
        )


def _loot_cases():
    cases, _ = hybrid.load_dev_cases()
    return [
        c
        for c in cases
        if c.id
        in {
            "spec217.dev.reg.loot.shop.buy",
            "spec217.dev.reg.loot.craft.forge",
            "spec217.dev.reg.npc.corvo.case",
        }
    ]


def test_run_stops_on_provider_error(tmp_path: Path) -> None:
    backend = _Backend(fail_at=2)
    ledger = loot.J1bLedger(tmp_path / "ledger.json")
    raw = run_phase(
        "j1b",
        _loot_cases(),
        lambda c: j1b_request(c.input),
        backend,
        ledger,
        tmp_path / "run",
        {"run_id": "t"},
    )
    assert raw["status"] == "blocked-by-provider" and backend.calls == 2
    assert ledger.read()["j1b_calls"] == 2


def test_summary_reproducible_and_scores_wrong_source(tmp_path: Path) -> None:
    cases, _ = hybrid.load_dev_cases()
    oracle = load_oracle()
    meta = {"run_id": "t", "dev_hash": "sha256:x", "oracle_hash": loot.ORACLE_SHA256}
    good = run_phase(
        "j1b",
        _loot_cases(),
        lambda c: j1b_request(c.input),
        _Backend(picks={"route": "loot", "loot_source": "shop"}),
        loot.J1bLedger(tmp_path / "l.json"),
        tmp_path / "run",
        meta,
    )
    reloaded = json.loads((tmp_path / "run" / "raw.json").read_text(encoding="utf-8"))
    summary = loot.summarize(reloaded, cases, oracle)
    assert hybrid.digest_of(summary) == hybrid.digest_of(loot.summarize(good, cases, oracle))
    assert "expected" not in json.dumps(reloaded)
    # Fake Jev says loot/shop everywhere: the guard drops the forge case (no trade
    # verb) and the npc case (no item verb); unguarded both become errors.
    assert summary["baseline"]["covered"] == 0
    assert summary["chosen"]["variant_id"] == "plain+target+guard@0.50+lootsrc+lguard@0.50"
    assert (
        summary["chosen"]["covered"] == 1 and summary["chosen"]["covered_loot_source_errors"] == 0
    )
    unguarded = next(v for v in summary["variants"] if v["variant_id"].endswith("+lootsrc@0.50"))
    assert unguarded["covered_loot_source_errors"] == 2 and unguarded["covered_route_errors"] == 1


def test_selection_requires_zero_errors_and_coverage_gain() -> None:
    base = {"covered": 5}
    ok = {
        "covered": 7,
        "covered_loot_source_errors": 0,
        "covered_route_errors": 0,
        "covered_target_errors": 0,
        "unsafe_combat_escalations": 0,
        "policy": {"loot_guard": False, "loot_tau": 0.5},
    }
    guard = {**ok, "policy": {"loot_guard": True, "loot_tau": 0.55}}
    assert loot.select([ok, guard], base) is guard  # tie → guard on
    assert loot.select([{**ok, "covered_loot_source_errors": 1}], base) is None
    assert loot.select([{**ok, "covered": 5}], base) is None  # no gain


def test_j1b_never_references_frozen_content() -> None:
    source = Path(loot.__file__).read_text(encoding="utf-8")
    assert "spec217_frozen.jsonl" not in source


def test_frozen_j1b_digest_matches_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """R7: the J1b freeze pins the J1 digest, the loot question, the guard and code."""
    frozen = loot.FROZEN_J1B_POLICY
    assert frozen.variant_id == "plain+target+guard@0.50+lootsrc+lguard@0.50"
    assert frozen.base == hybrid.FROZEN_J1_POLICY
    assert loot.structure_digest(frozen) == loot.FROZEN_J1B_STRUCTURE_DIGEST
    assert loot.structure_digest(LootPolicy(loot_guard=False)) != loot.FROZEN_J1B_STRUCTURE_DIGEST
    assert loot.structure_digest(LootPolicy(loot_tau=0.55)) != loot.FROZEN_J1B_STRUCTURE_DIGEST
    monkeypatch.setattr(hybrid, "_source", lambda fn: "edited")  # J1 code edit breaks it too
    assert loot.structure_digest(frozen) != loot.FROZEN_J1B_STRUCTURE_DIGEST


# ---------------------------------------------------------------------------
# Astra review (handoffs/SPEC-238-ASTRA-review.md)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "verbs"),
    [
        ("SHOP", ("take",)),
        ("CRAFT", ("take",)),
        ("SHOP", ()),
        ("CRAFT", ("trade",)),
    ],
)
def test_guard_fails_closed_without_location(source, verbs) -> None:
    """Unknown location (None) never satisfies SHOP/CRAFT; only a verb can."""
    assert not loot_guard_ok(source, verbs, None, None)
    assert not loot_guard_ok(source, verbs, False, False)


def test_dev_never_exercised_location_features() -> None:
    """Every J1b DEV sample case had an unknown location: the run measured verb-only."""
    cases, _ = hybrid.load_dev_cases()
    for case in j1b_sample(eligible_cases(cases)):
        assert loot_features(case.input.get("state") or {}) == {
            "merchant_here": None,
            "craft_station": None,
        }, case.id


def test_frozen_j2_request_drops_location_features() -> None:
    assert loot.FROZEN_J1B_LOCATION_FEATURES is False
    case_input = {
        "action": "Pego a espada",
        "state": {"world": {"current_location_id": "na_anel_dourado"}},
    }
    assert j1b_request(case_input).wire_body()["state"]["merchant_here"] is True
    frozen = loot.frozen_j1b_request(case_input).wire_body()
    assert "merchant_here" not in frozen["state"] and "craft_station" not in frozen["state"]
    j1 = hybrid.frozen_request(case_input, hybrid.FROZEN_J1_POLICY).wire_body()
    assert frozen["state"] == j1["state"]
    assert frozen["questions"]["route"] == j1["questions"]["route"]
    assert frozen["questions"]["loot_source"] == loot.LOOT_SOURCE_QUESTION.model_dump(
        exclude_none=True
    )


def test_frozen_j2_decision_ignores_location_relaxation() -> None:
    kwargs = dict(
        route=_ans("loot"),
        target=None,
        verbs=("take",),
        in_combat=False,
        target_status="no_candidates",
        merchant_here=True,
        craft_station=True,
    )
    assert loot.frozen_loot_decision(loot_source=_ans("shop"), **kwargs)["reason"] == "loot_guard"
    assert loot.frozen_loot_decision(loot_source=_ans("craft"), **kwargs)["reason"] == "loot_guard"
    ok = loot.frozen_loot_decision(loot_source=_ans("treasure"), **kwargs)
    assert ok["source"] == "jev" and ok["loot_source"] == "TREASURE"
    traded = loot.frozen_loot_decision(loot_source=_ans("shop"), **{**kwargs, "verbs": ("trade",)})
    assert traded["loot_source"] == "SHOP"


def _obs(**kw):
    base = {
        "case_id": "c",
        "replicate": 1,
        "b_source": "jev",
        "b_route": "loot",
        "b_loot_source": "SHOP",
        "a_route": "loot",
        "a_loot_source": "SHOP",
        "oracle_loot_source": None,
    }
    return {**base, **kw}


def test_r9_7_prefers_the_oracle_label() -> None:
    assert loot.r9_7_loot_source([_obs(oracle_loot_source="SHOP", a_loot_source="TREASURE")])[
        "pass"
    ]
    bad = loot.r9_7_loot_source([_obs(oracle_loot_source="TREASURE")])
    assert not bad["pass"] and bad["errors"] == 1  # A agreeing with B does not save it


def test_r9_7_falls_back_to_arm_a_and_fails_closed() -> None:
    assert loot.r9_7_loot_source([_obs()])["pass"]
    assert not loot.r9_7_loot_source([_obs(a_loot_source="CRAFT")])["pass"]
    unverifiable = loot.r9_7_loot_source([_obs(a_route="npc_actor", a_loot_source=None)])
    assert not unverifiable["pass"] and unverifiable["unverifiable"] == 1


def test_r9_7_scope_is_jev_covered_loot_only() -> None:
    result = loot.r9_7_loot_source(
        [
            _obs(b_source="fallback", b_loot_source="CRAFT"),
            _obs(b_route="npc_actor", b_loot_source=None),
        ]
    )
    assert result == {
        "rule": "R9.7",
        "checked": 0,
        "errors": 0,
        "unverifiable": 0,
        "failures": [],
        "pass": True,
    }


def test_frozen_j2_request_equals_the_measured_dev_requests() -> None:
    """On DEV (no location) the J2 request is exactly the J1b request that was run."""
    cases, _ = hybrid.load_dev_cases()
    for case in j1b_sample(eligible_cases(cases)):
        assert (
            loot.frozen_j1b_request(case.input).wire_body() == j1b_request(case.input).wire_body()
        ), case.id
