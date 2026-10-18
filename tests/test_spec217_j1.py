"""SPEC-217 J1: structured Jev router decisions — offline, no provider traffic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.experiments import jev_router_hybrid as hybrid
from evals.experiments.jev_router_hybrid import (
    CLASSIFY_REFERENCE_MS, Case, Policy, decision_state, extract_verbs,
    frozen_request, hybrid_decision, load_dev_cases, scene_view, score_policy,
    screening_request, select, summarize, target_question,
)
from evals.experiments.spec217_j1 import BudgetExhausted, CallLedger, run_phase
from services.jev_decision import (
    ChoiceAnswer, DecisionRequest, DecisionResult, DecisionState, JevRateLimitError,
)
from services.jev_rollout import _request as rollout_request


NPCS = {
    "Corvo": {"id": "npc_corvo_rapido", "name": "Corvo", "in_scene": True,
              "known_by_player": True, "aliases": ["Corvo Cinzento"]},
    "Magda": {"id": "npc_velha_magda", "name": "Magda", "in_scene": False, "known_by_player": True},
    "Sombra": {"id": "npc_sombra", "name": "Sombra", "in_scene": True,
               "known_by_player": False, "visibility": "secret"},
}


def test_features_are_deterministic_and_public_only() -> None:
    state = decision_state({"action": "  FALO COM CORVO  ", "state": {"npcs": NPCS,
                                                                    "active_npc_name": "Corvo"}})
    assert state == decision_state({"action": "  FALO COM CORVO  ",
                                    "state": {"npcs": NPCS, "active_npc_name": "Corvo"}})
    assert state.action == "falo com corvo"
    assert [actor.id for actor in state.scene] == ["npc_corvo_rapido"]  # secret/off-scene dropped
    assert state.scene[0].aliases == ("Corvo Cinzento",)
    assert state.last_speaker == "npc_corvo_rapido"
    assert state.verbs == ("talk",)
    wire = json.dumps(DecisionRequest(state=state, questions={
        "route": hybrid.PLAIN_ROUTE_QUESTION}).wire_body(), ensure_ascii=False)
    assert "Sombra" not in wire and "npc_sombra" not in wire and "Magda" not in wire


@pytest.mark.parametrize(("action", "verbs"), [
    ("Ataco o guarda", ("attack",)), ("Golpeio o degolador", ("attack",)),
    ("Limpo minha espada enquanto espero", ("rest",)), ("Guardo o arco na mochila", ()),
    ("ei, Grum!", ("talk",)), ("Compro uma poção", ("trade",)), ("Forjo um elmo", ("craft",)),
    ("Observo o lobo de longe", ("observe",)), ("Digo a Silas que nao quero briga", ("talk",)),
])
def test_verb_flags_are_a_closed_lexicon(action: str, verbs: tuple[str, ...]) -> None:
    assert extract_verbs(action) == verbs


def test_production_rollout_payload_is_unchanged() -> None:
    body = rollout_request({"world": {"current_location": "X"}}, "olho").wire_body()
    assert set(body["state"]) == {"action", "location_id", "in_combat"}


def test_two_stage_target_restricted_to_scene_candidates() -> None:
    view = scene_view({"npcs": NPCS})
    question = target_question(view.actors)
    assert set(question.criteria) == {"npc_corvo_rapido", "none"}
    assert "Corvo Cinzento" in question.criteria["npc_corvo_rapido"]
    assert target_question(()) is None
    many = {"enemies": [{"id": f"enemy_{i:02d}", "name": f"G{i}", "status": "ativo"} for i in range(21)]}
    over = scene_view(many)
    assert over.target_status == "unrepresentable" and over.actors == ()
    assert decision_state({"action": "ataco", "state": many}).scene is None  # never truncated


def test_screening_and_frozen_requests_have_expected_questions() -> None:
    case_input = {"action": "Falo com Corvo", "state": {"npcs": NPCS}}
    assert set(screening_request(case_input).questions) == {
        "route_legacy", "route_plain", "route_rich", "target"}
    frozen = frozen_request(case_input, Policy("plain", True, True))
    assert set(frozen.questions) == {"route", "target"}
    assert set(frozen_request(case_input, Policy("rich", False, True)).questions) == {"route"}


def _route(choice: str, confidence: float = 0.9) -> dict:
    return {"choice": choice, "confidence": confidence}


@pytest.mark.parametrize(("route", "verbs", "status", "target", "reason"), [
    (_route("none"), (), "no_candidates", None, "abstain"),
    (_route("storyteller", 0.4), (), "no_candidates", None, "low_confidence"),
    (_route("loot"), ("trade",), "no_candidates", None, "loot_context_out_of_scope"),
    (_route("combat_agent"), ("talk",), "ok", _route("npc_x"), "combat_guard"),
    (_route("npc_actor"), ("talk",), "unrepresentable", None, "target_unrepresentable"),
    (_route("npc_actor"), ("talk",), "ok", _route("npc_x", 0.3), "target_low_confidence"),
])
def test_hybrid_policy_falls_back_when_not_confident_or_representable(
    route, verbs, status, target, reason,
) -> None:
    decision = hybrid_decision(route=route, target=target, verbs=verbs, in_combat=False,
                               target_status=status, policy=Policy("plain", True, True))
    assert decision == {"source": "fallback", "reason": reason, "route": None, "target": None}


def test_hybrid_policy_uses_jev_only_when_confident_and_representable() -> None:
    policy = Policy("plain", True, True)
    talk = hybrid_decision(route=_route("npc_actor"), target=_route("npc_x"), verbs=("talk",),
                           in_combat=False, target_status="ok", policy=policy)
    assert talk == {"source": "jev", "reason": None, "route": "npc_actor", "target": "npc_x"}
    story = hybrid_decision(route=_route("storyteller"), target=None, verbs=(),
                            in_combat=False, target_status="no_candidates", policy=policy)
    assert story["source"] == "jev" and story["target"] is None
    route_only = hybrid_decision(route=_route("npc_actor"), target=None, verbs=("talk",),
                                 in_combat=False, target_status="ok",
                                 policy=Policy("plain", False, True))
    assert route_only["reason"] == "target_not_in_structure"


def _p1_row(case_id: str, choice: str, confidence: float = 0.9, latency: int = 300,
            kind: str = "route", target: dict | None = None, verbs=("observe",)) -> dict:
    answers = {f"route_{label}": _route(choice, confidence) for label in hybrid.LABEL_SETS}
    if target:
        answers["target"] = target
    return {"case_id": case_id, "kind": kind, "verbs": list(verbs), "in_combat": False,
            "target_status": "ok" if target else "no_candidates", "answers": answers,
            "latency_ms": latency}


def test_fallback_latency_is_sum_and_unsafe_escalation_is_counted() -> None:
    rows = [_p1_row("a", "storyteller"), _p1_row("b", "none"),
            _p1_row("c", "combat_agent", verbs=("attack",))]
    expected = {"a": {"route": "storyteller", "target": None},
                "b": {"route": "storyteller", "target": None},
                "c": {"route": "storyteller", "target": None}}
    score = score_policy(rows, expected, {}, Policy("plain", True, False))
    assert score["covered"] == 2 and score["unsafe_combat_escalations"] == 1
    only_fallback = score_policy(rows[1:2], expected, {}, Policy("plain", True, False))
    assert only_fallback["hybrid_latency_estimate_ms_p50"] == 300 + CLASSIFY_REFERENCE_MS["p50"]
    assert only_fallback["jev_latency_ms_p50"] == 300
    assert score["fallback_reasons"] == {"abstain": 1}
    assert not hybrid.feasible(score)


def test_selection_prefers_feasible_coverage_then_tau_near_default() -> None:
    def fake(label, tau, covered, errors=0, unsafe=0):
        return {"policy": {"label_set": label, "tau": tau, "with_target": True,
                           "combat_guard": True}, "covered": covered,
                "covered_route_errors": errors, "covered_target_errors": 0,
                "unsafe_combat_escalations": unsafe}
    chosen = select([fake("rich", 0.5, 40, unsafe=1), fake("plain", 0.6, 30),
                     fake("legacy", 0.5, 30), fake("plain", 0.5, 30)])
    assert chosen["policy"] == {"label_set": "plain", "tau": 0.5, "with_target": True,
                                "combat_guard": True}


def test_dev_hash_mismatch_aborts(tmp_path: Path) -> None:
    corpus = tmp_path / "dev.jsonl"
    corpus.write_text("{}\n", encoding="utf-8")
    lock = tmp_path / "dev.sha256"
    lock.write_text("sha256:00", encoding="utf-8")
    with pytest.raises(hybrid.CorpusError):
        load_dev_cases(corpus, lock)
    cases, digest = load_dev_cases()
    assert len(cases) == 59 and digest == hybrid.DEV_SHA256


def test_j1_never_references_frozen_content() -> None:
    for module in ("jev_router_hybrid.py", "spec217_j1.py"):
        source = (Path(hybrid.__file__).parent / module).read_text(encoding="utf-8")
        assert "spec217_frozen.jsonl" not in source


def test_budget_ledger_caps_j1_60_and_persists(tmp_path: Path) -> None:
    ledger = CallLedger(tmp_path / "ledger.json", j1_cap=60, total_cap=160)
    for index in range(60):
        ledger.consume("p1", f"case{index}")
    with pytest.raises(BudgetExhausted):
        CallLedger(tmp_path / "ledger.json").consume("p1", "late")  # survives restart
    assert CallLedger(tmp_path / "ledger.json").read()["total_calls"] == 60
    total = CallLedger(tmp_path / "t.json", j1_cap=500, total_cap=160)
    for index in range(160):
        total.consume("p1", str(index))
    with pytest.raises(BudgetExhausted):
        total.consume("p1", "x")


class _Backend:
    def __init__(self, fail_at: int | None = None) -> None:
        self.calls = 0
        self.fail_at = fail_at

    def decide(self, request, *, idempotency_key=None, correlation_id=None):
        self.calls += 1
        if self.calls == self.fail_at:
            raise JevRateLimitError("Jev HTTP 429")
        answers = {}
        for name, question in request.questions.items():
            keys = list(question.criteria)
            probabilities = {key: (0.9 if index == 0 else 0.1 / (len(keys) - 1))
                             for index, key in enumerate(keys)}
            answers[name] = ChoiceAnswer(type="choice", choice=keys[0],
                                         probabilities=probabilities, confidence=0.9)
        return DecisionResult(model="jev-test", answers=answers, usage=None,
                              correlation_id="c", latency_ms=5)


def _cases() -> list[Case]:
    return [Case(id=f"c{i}", kind="route", input={"action": "Observo a praça", "state": {}},
                 expected={"route": "storyteller", "target": None}, python_gate=False,
                 critical=None) for i in range(3)]


def test_run_stops_on_provider_error(tmp_path: Path) -> None:
    backend = _Backend(fail_at=2)
    ledger = CallLedger(tmp_path / "ledger.json")
    raw = run_phase("p1", _cases(), lambda case: screening_request(case.input), backend,
                    ledger, tmp_path / "run", {"run_id": "t"})
    assert raw["status"] == "blocked-by-provider" and backend.calls == 2
    assert ledger.read()["total_calls"] == 2
    assert raw["p1"]["rows"][1]["error"] == "rate_limit"
    persisted = json.loads((tmp_path / "run" / "raw.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "blocked-by-provider"


def test_summary_reproducible_from_raw(tmp_path: Path) -> None:
    raw = run_phase("p1", _cases(), lambda case: screening_request(case.input), _Backend(),
                    CallLedger(tmp_path / "ledger.json"), tmp_path / "run",
                    {"run_id": "t", "dev_hash": "sha256:x"})
    assert raw["status"] == "complete"
    reloaded = json.loads((tmp_path / "run" / "raw.json").read_text(encoding="utf-8"))
    assert hybrid.digest_of(summarize(reloaded, _cases())) == hybrid.digest_of(summarize(raw, _cases()))
    assert "expected" not in json.dumps(reloaded)  # raw holds no oracle labels


def test_decision_state_rejects_unbounded_scene() -> None:
    actor = {"id": "npc_a", "name": "A", "kind": "npc"}
    with pytest.raises(ValueError):
        DecisionState(action="x", scene=tuple({**actor, "id": f"npc_{i}"} for i in range(21)))
    with pytest.raises(ValueError):
        DecisionState(action="x", scene=({**actor, "id": "bad id"},))


def test_frozen_structure_digest_matches_code() -> None:
    """R6: the J1 freeze covers questions, target stage, verbs, features and τ."""
    assert hybrid.FROZEN_J1_POLICY.variant_id == "plain+target@0.50"
    assert hybrid.structure_digest(hybrid.FROZEN_J1_POLICY) == hybrid.FROZEN_J1_STRUCTURE_DIGEST
    assert hybrid.structure_digest(Policy("rich", True, False)) != hybrid.FROZEN_J1_STRUCTURE_DIGEST
