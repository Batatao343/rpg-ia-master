"""SPEC-217 J2 runner + R9 rule — offline, no provider traffic, FROZEN never opened."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.core.hashing import sha256_file
from evals.experiments import jev_router_hybrid as hybrid
from evals.experiments import spec217_j2 as j2
from evals.experiments.jev_router_hybrid import Case, CorpusError
from evals.experiments.spec217_j1 import BudgetExhausted
from services.jev_decision import ChoiceAnswer, DecisionResult, JevRateLimitError

# ---------------------------------------------------------------------------
# Freeze, inputs, single run, ledger
# ---------------------------------------------------------------------------

def test_frozen_structure_and_oracle_seals_match() -> None:
    structure = j2.verify_frozen_structure()
    assert structure["variant_id"] == "plain+target+guard@0.50+lootsrc+lguard@0.50"
    assert structure["j1b_structure_digest"].startswith("sha256:75635c89")
    assert hybrid.FROZEN_SHA256.startswith("sha256:442725e5")
    assert sha256_file(j2.FROZEN_ORACLE) == j2.FROZEN_ORACLE_SHA256
    assert j2.FROZEN_ORACLE_SHA256.startswith("sha256:d9c860ec")


def test_frozen_and_oracle_hash_mismatch_abort(tmp_path: Path) -> None:
    corpus, lock = tmp_path / "f.jsonl", tmp_path / "f.sha256"
    corpus.write_text('{"split": "frozen"}\n', encoding="utf-8")
    lock.write_text(sha256_file(corpus), encoding="utf-8")
    with pytest.raises(CorpusError):  # matches its lock, not the spec seal
        j2.load_frozen_cases(corpus, lock)
    oracle = tmp_path / "o.json"
    oracle.write_text('{"labels": {}}', encoding="utf-8")
    (tmp_path / "o.sha256").write_text(sha256_file(oracle), encoding="utf-8")
    with pytest.raises(CorpusError):
        j2.load_frozen_oracle(oracle, tmp_path / "o.sha256")


def test_location_features_must_stay_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(j2.loot, "FROZEN_J1B_LOCATION_FEATURES", True)
    with pytest.raises(CorpusError):
        j2.verify_frozen_structure()


def test_budget_is_exactly_the_j2_cap() -> None:
    assert j2.required_calls(16) == 100 == j2.J2_CALL_CAP


def test_ledger_caps_j2_100_and_total_190(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({"spec": "SPEC-217", "j1_calls": 60, "j1b_calls": 30,
                                "total_calls": 90, "entries": []}), encoding="utf-8")
    ledger = j2.J2Ledger(path)
    assert ledger.remaining() == 100
    for index in range(100):
        ledger.consume("j2", f"c{index}", "jev")
    with pytest.raises(BudgetExhausted):
        j2.J2Ledger(path).consume("j2", "late", "classify")  # survives restart
    data = j2.J2Ledger(path).read()
    assert data["j2_calls"] == 100 and data["total_calls"] == 190 and data["j1b_calls"] == 30
    total = j2.J2Ledger(tmp_path / "t.json", j2_cap=500, total_cap=3)
    for index in range(3):
        total.consume("j2", str(index), "jev")
    with pytest.raises(BudgetExhausted):
        total.consume("j2", "x", "jev")


def test_second_run_is_refused_without_owner_authorization(tmp_path: Path) -> None:
    marker, ledger = tmp_path / "runs" / "J2_STARTED.json", j2.J2Ledger(tmp_path / "ledger.json")
    j2.claim_single_run(marker, ledger, "run-1")
    with pytest.raises(CorpusError):
        j2.claim_single_run(marker, ledger, "run-2")
    marker.unlink()  # the ledger stamp alone still refuses
    with pytest.raises(CorpusError):
        j2.claim_single_run(marker, ledger, "run-2")
    j2.claim_single_run(marker, ledger, "run-2", owner_rerun_authorization="dono: repetir")
    assert [run["run_id"] for run in ledger.read()["j2_runs"]] == ["run-1", "run-2"]


def test_pairing_plan_is_seeded_complete_and_declares_arm_order() -> None:
    ids = [f"c{i:02d}" for i in range(16)]
    plan = j2.pairing_plan(ids)
    assert plan == j2.pairing_plan(list(reversed(ids)))
    assert [rep["replicate"] for rep in plan] == [1, 2, 3]
    for rep in plan:
        assert sorted(item["case_id"] for item in rep["order"]) == ids
        assert {item["first_arm"] for item in rep["order"]} <= {"a", "b"}
    assert plan[0]["order"] != plan[1]["order"]
    assert {item["first_arm"] for rep in plan for item in rep["order"]} == {"a", "b"}


def test_sanity_case_reaches_classify_and_is_outside_dev() -> None:
    eligible, gates = j2._gate_probe([j2.SANITY_CASE])
    assert eligible == [j2.SANITY_CASE] and gates == {}
    dev, _ = hybrid.load_dev_cases()
    j2.sanity_outside_corpora(j2.SANITY_CASE, dev)
    clash = Case(id="x", kind="route", input={"action": j2.SANITY_CASE.input["action"].upper()},
                 expected={}, python_gate=False, critical=None)
    with pytest.raises(CorpusError):
        j2.sanity_outside_corpora(j2.SANITY_CASE, [clash])


def test_only_the_j2_runner_names_the_frozen_corpus() -> None:
    folder = Path(hybrid.__file__).parent
    for module in ("jev_router_hybrid.py", "spec217_j1.py", "spec238_loot.py"):
        assert "spec217_frozen.jsonl" not in (folder / module).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CLASSIFY stop rule (R10)
# ---------------------------------------------------------------------------

_OK = {"outcome": "success", "fell_back": False, "attempt_index": 0}


@pytest.mark.parametrize(("attempts", "violation"), [
    ([_OK], None),
    ([], "no_attempt"),
    ([{**_OK, "outcome": "invoke_error"}], "outcome_invoke_error"),
    ([{**_OK, "fell_back": True}], "fell_back"),
    ([{**_OK, "attempt_index": 1}], "retry"),
    ([{**_OK, "outcome": "invalid_structured"}, {**_OK, "attempt_index": 1}], "extra_attempt"),
])
def test_classify_stop_rule(attempts, violation) -> None:
    assert j2.classify_violation(attempts) == violation


class _FakeClient:
    def __init__(self, fail: bool, loot_context: str | None = "SHOP") -> None:
        self.fail, self.loot_context, self.calls = fail, loot_context, 0

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def invoke(self, _input):
        from langchain_core.messages import AIMessage

        from agents.router import RouterDecision

        self.calls += 1
        if self.fail:
            raise TimeoutError("provider timeout")
        return {"raw": AIMessage(content="", usage_metadata={"input_tokens": 10, "output_tokens": 2,
                                                             "total_tokens": 12}),
                "parsed": RouterDecision(route="loot", loot_context=self.loot_context, target=None,
                                         reasoning="t", confidence=0.9),
                "parsing_error": None}


def _live_classify(monkeypatch, tmp_path: Path, first_fails: bool):
    import agents.router as router
    import llm_setup

    clients = {"p1": _FakeClient(first_fails), "p2": _FakeClient(False)}
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda provider, *_a: clients[provider])
    monkeypatch.setattr(router, "get_llm", lambda *a, **k: llm_setup.RoutedLLM(
        llm_setup.ModelTier.CLASSIFY, 0.0, [("p1", "m"), ("p2", "m")]))
    ledger = j2.J2Ledger(tmp_path / "ledger.json")
    return j2.live_classify(ledger), ledger, clients


def test_arm_a_records_route_and_loot_context(monkeypatch, tmp_path: Path) -> None:
    classify, ledger, clients = _live_classify(monkeypatch, tmp_path, first_fails=False)
    record = classify(j2.SANITY_CASE, "j2-sanity")
    assert record["route"] == "loot" and record["loot_source_effective"] == "SHOP"
    assert record["loot_context_raw"] == "SHOP" and record["error"] is None
    assert ledger.read()["j2_calls"] == 1 and clients["p2"].calls == 0


def test_arm_a_fallback_is_refused_before_network(monkeypatch, tmp_path: Path) -> None:
    classify, ledger, clients = _live_classify(monkeypatch, tmp_path, first_fails=True)
    with pytest.raises(j2.ProviderStop):
        classify(j2.SANITY_CASE, "j2-sanity")
    assert ledger.read()["j2_calls"] == 1  # only the failed first attempt was spent
    assert clients["p2"].calls == 0


# ---------------------------------------------------------------------------
# Runner with fake arms
# ---------------------------------------------------------------------------

def _ans(choice: str, confidence: float = 0.9) -> dict:
    return {"choice": choice, "confidence": confidence, "probabilities": {choice: confidence}}


def _cases() -> list[Case]:
    npcs = {"Brisa": {"id": "npc_brisa_teste", "name": "Brisa", "in_scene": True,
                      "known_by_player": True, "aliases": ["Brisinha"]}}
    return [
        Case("e1", "route", {"action": "Observo o rio", "state": {}},
             {"route": "storyteller", "target": None}, False, None),
        Case("e2", "route", {"action": "Pego as moedas", "state": {}},
             {"route": "loot", "target": None}, False, None),
        Case("e3", "target", {"action": "Falo com Brisinha", "state": {"npcs": npcs}},
             {"route": "npc_actor", "target": "npc_brisa_teste"}, False, None),
        Case("g1", "route", {"action": "Viajo para X", "state": {}},
             {"route": "storyteller", "target": None}, True, None),
    ]


def _fake_arms(ledger: j2.J2Ledger, fail_jev_at: int | None = None):
    jev_answers = {"e1": {"route": _ans("storyteller"), "loot_source": _ans("none")},
                   "e2": {"route": _ans("loot"), "loot_source": _ans("treasure")},
                   "e3": {"route": _ans("npc_actor"), "target": _ans("none", 0.3),
                          "loot_source": _ans("none")},
                   j2.SANITY_CASE.id: {"route": _ans("storyteller"), "loot_source": _ans("none")}}
    a_answers = {"e1": ("storyteller", None, None), "e2": ("loot", None, "TREASURE"),
                 "e3": ("npc_actor", "Brisa", None), j2.SANITY_CASE.id: ("storyteller", None, None)}
    counter = {"jev": 0}

    def classify(case: Case, phase: str) -> dict:
        ledger.consume(phase, case.id, "classify")
        route, target, source = a_answers[case.id]
        return {"route": route, "target_raw": target, "loot_source_effective": source,
                "loot_context_raw": source, "latency_ms": 1500, "attempts": [_OK],
                "usage": [{"input_tokens": 5, "output_tokens": 1}], "error": None}

    def jev(case: Case, phase: str) -> dict:
        ledger.consume(phase, case.id, "jev")
        counter["jev"] += 1
        if counter["jev"] == fail_jev_at:
            raise j2.ProviderStop("rate_limit")
        return {"answers": jev_answers[case.id], "latency_ms": 300, "error": None}

    return classify, jev


def _run(tmp_path: Path, fail_jev_at: int | None = None) -> tuple[dict, j2.J2Ledger]:
    ledger = j2.J2Ledger(tmp_path / "ledger.json")
    classify, jev = _fake_arms(ledger, fail_jev_at)
    cases = _cases()
    raw = j2.run_j2(eligible=cases[:3], gates={"g1": "storyteller"}, sanity=j2.SANITY_CASE,
                    classify=classify, jev=jev, ledger=ledger, output_dir=tmp_path / "run",
                    meta={"run_id": "t", "frozen_hash": "sha256:x", "frozen_oracle_hash": "sha256:y",
                          "variant_id": "v", "r9_7_reference": "oracle"})
    return raw, ledger


def test_run_spends_sanity_plus_pairs_and_gates_spend_nothing(tmp_path: Path) -> None:
    raw, ledger = _run(tmp_path)
    assert raw["status"] == "complete"
    assert ledger.read()["j2_calls"] == j2.required_calls(3) == 4 + 2 * 3 * 3
    assert [entry["arm"] for entry in raw["sanity"]] == ["a", "b", "a", "b"]
    gates = [row for row in raw["rows"] if row["python_gate"]]
    assert len(gates) == 3 and all(row["a"]["calls"] == row["b"]["calls"] == 0 for row in gates)
    persisted = json.loads((tmp_path / "run" / "raw.json").read_text(encoding="utf-8"))
    assert persisted["pairing_plan"] == raw["pairing_plan"]
    assert "expected" not in json.dumps(persisted)  # raw holds no oracle labels


def test_run_stops_on_provider_error_without_score(tmp_path: Path) -> None:
    raw, ledger = _run(tmp_path, fail_jev_at=3)
    assert raw["status"] == "blocked-by-provider"
    summary = j2.summarize(raw, _cases(), {"e2": "TREASURE"})
    assert summary["status"] == "blocked-by-provider" and "results" not in summary
    assert ledger.read()["j2_calls"] < j2.required_calls(3)


def test_summary_reproducible_and_fallback_uses_arm_a(tmp_path: Path) -> None:
    raw, _ = _run(tmp_path)
    reloaded = json.loads((tmp_path / "run" / "raw.json").read_text(encoding="utf-8"))
    oracle = {"e2": "TREASURE"}
    summary = j2.summarize(reloaded, _cases(), oracle)
    assert hybrid.digest_of(summary) == hybrid.digest_of(j2.summarize(raw, _cases(), oracle))
    obs = {(o["case_id"], o["replicate"]): o for o in summary["observations"]}
    e3 = obs[("e3", 1)]  # target low confidence -> CLASSIFY of the same case/replicate
    assert e3["b_source"] == "fallback" and e3["b_target"] == "npc_brisa_teste" == e3["a_target"]
    assert e3["b_latency_ms"] == 1800.0
    e2 = obs[("e2", 1)]
    assert e2["b_source"] == "jev" and e2["b_loot_source"] == "TREASURE" and e2["b_latency_ms"] == 300.0
    results = summary["results"]
    assert results["r9_7"]["checked"] == 3 and results["r9_7"]["pass"]
    assert results["r9_5"]["pass"] and results["r9_6"]["pass"]
    assert results["r9_1"]["paired_losses"] == 0
    # p50: B = [300]*6 + [1800]*3 -> 300; A = 1500 -> gain 1200; p95(B)=1800 > 1.10*1500
    assert results["r9_4"]["p50_gain_ms"] == 1200.0 and not results["r9_4"]["pass"]
    assert summary["verdict"] == "NO_GO"
    assert summary["calls"]["j2_total"] == 22


# ---------------------------------------------------------------------------
# R9 rule (pure)
# ---------------------------------------------------------------------------

def _obs(expected="storyteller", a="storyteller", b="storyteller", **kw) -> dict:
    return {"case_id": kw.get("case_id", "c"), "replicate": kw.get("replicate", 1),
            "kind": kw.get("kind", "route"), "expected_route": expected,
            "expected_target": kw.get("expected_target"), "a_route": a, "b_route": b,
            "a_target": kw.get("a_target"), "b_target": kw.get("b_target"),
            "b_target_in_candidates": kw.get("inside", True), "b_source": kw.get("b_source", "jev"),
            "a_latency_ms": kw.get("a_lat", 1500.0), "b_latency_ms": kw.get("b_lat", 300.0),
            "jev_latency_ms": 300.0}


def test_r9_1_non_inferiority_and_paired_losses() -> None:
    base = [_obs() for _ in range(47)]
    one_loss = base + [_obs(b="npc_actor")]
    assert j2.r9_1_route(one_loss)["pass"]  # 47/48 vs 48/48 = -2.08 pp, 1 loss
    two_losses = [_obs() for _ in range(46)] + [_obs(b="npc_actor")] * 2
    result = j2.r9_1_route(two_losses)
    assert result["paired_losses"] == 2 and not result["pass"]
    swap = [_obs() for _ in range(46)] + [_obs(a="npc_actor", b="storyteller"),
                                          _obs(a="storyteller", b="loot")]
    assert j2.r9_1_route(swap)["pass"]  # 1 win, 1 loss
    assert not j2.r9_1_route([])["pass"]


def test_r9_1_margin_is_two_and_a_half_points() -> None:
    # 10 obs: A 10/10; B 9/10 = -10 pp even with a single loss -> NO_GO
    obs = [_obs() for _ in range(9)] + [_obs(b="loot")]
    result = j2.r9_1_route(obs)
    assert result["paired_losses"] == 1 and not result["pass"]


def test_r9_2_target_accuracy_and_candidates() -> None:
    good = _obs("npc_actor", "npc_actor", "npc_actor", kind="target", expected_target="n1",
                a_target="n1", b_target="n1")
    worse = {**good, "b_target": None}
    assert j2.r9_2_target([good])["pass"]
    assert not j2.r9_2_target([worse])["pass"]
    assert not j2.r9_2_target([{**good, "b_target_in_candidates": False}])["pass"]
    better = {**good, "a_target": None}
    assert j2.r9_2_target([better])["pass"]


def test_decision_rule_no_go_on_unsafe_combat_escalation() -> None:
    unsafe = _obs("npc_actor", "npc_actor", "combat_agent")
    assert not j2.r9_3_unsafe([unsafe])["pass"]
    # an A error inherited through fallback is still a final B decision
    inherited = _obs("npc_actor", "combat_agent", "combat_agent", b_source="fallback")
    assert not j2.r9_3_unsafe([inherited])["pass"]
    assert j2.r9_3_unsafe([_obs("combat_agent", "combat_agent", "combat_agent")])["pass"]


def test_decision_rule_no_go_on_latency_gain_below_500ms() -> None:
    small = [_obs(a_lat=1000.0, b_lat=600.0) for _ in range(10)]
    assert j2.r9_4_latency(small)["p50_gain_ms"] == 400.0 and not j2.r9_4_latency(small)["pass"]
    fat_tail = [_obs(a_lat=1500.0, b_lat=300.0) for _ in range(18)] + [
        _obs(a_lat=1500.0, b_lat=1800.0)] * 2
    assert not j2.r9_4_latency(fat_tail)["pass"]  # p95 ratio 1.2
    ok = [_obs(a_lat=1500.0, b_lat=300.0) for _ in range(19)] + [_obs(a_lat=1500.0, b_lat=1600.0)]
    result = j2.r9_4_latency(ok)
    assert result["pass"] and result["p95_ratio_b_over_a"] <= 1.10


def test_r9_5_gates_and_r9_6_provider() -> None:
    gate = {"case_id": "g", "replicate": 1, "a_route": "storyteller", "b_route": "storyteller",
            "calls": 0, "expected_route": "storyteller"}
    assert j2.r9_5_gates([gate])["pass"]
    assert not j2.r9_5_gates([{**gate, "calls": 1}])["pass"]
    assert not j2.r9_5_gates([])["pass"]
    raw = {"status": "complete", "sanity": [{"arm": "a", "error": None}],
           "rows": [{"case_id": "c", "a": {"error": "timeout"}, "b": {"error": None}}]}
    assert not j2.r9_6_provider(raw)["pass"]
    assert not j2.r9_6_provider({"status": "blocked-by-provider", "sanity": [], "rows": []})["pass"]


def test_verdict_requires_every_rule() -> None:
    assert j2.r9_verdict({"r9_1": {"pass": True}, "r9_7": {"pass": True}}) == "GO"
    assert j2.r9_verdict({"r9_1": {"pass": True}, "r9_7": {"pass": False}}) == "NO_GO"
    assert j2.r9_verdict({}) == "NO_GO"


def test_map_target_to_id_uses_the_same_scene_view() -> None:
    state = _cases()[2].input["state"]
    assert j2.map_target_to_id(state, "Brisa") == "npc_brisa_teste"
    assert j2.map_target_to_id(state, "brisinha") == "npc_brisa_teste"
    assert j2.map_target_to_id(state, "Inimigos") is None
    assert j2.map_target_to_id(state, None) is None


def test_jev_call_records_request_digest_and_stops_on_error(tmp_path: Path) -> None:
    class Backend:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        def decide(self, request, *, idempotency_key=None, correlation_id=None):
            if self.fail:
                raise JevRateLimitError("Jev HTTP 429")
            answers = {name: ChoiceAnswer(type="choice", choice=list(q.criteria)[0],
                                          probabilities={list(q.criteria)[0]: 1.0}, confidence=1.0)
                       for name, q in request.questions.items()}
            return DecisionResult(model="jev-test", answers=answers, usage=None,
                                  correlation_id="c", latency_ms=5)

    ledger = j2.J2Ledger(tmp_path / "ledger.json")
    row = j2.jev_call(Backend(False), ledger, "t")(_cases()[2], "j2-r1")
    assert row["request_digest"] == hybrid.digest_of(
        j2.loot.frozen_j1b_request(_cases()[2].input).wire_body())
    assert set(row["questions"]) == {"route", "target", "loot_source"}
    with pytest.raises(j2.ProviderStop):
        j2.jev_call(Backend(True), ledger, "t")(_cases()[0], "j2-r1")
    assert ledger.read()["j2_calls"] == 2
