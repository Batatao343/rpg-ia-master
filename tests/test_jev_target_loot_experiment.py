"""Offline source and artifact checks for the frozen SPEC-179 experiment."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from contextlib import contextmanager
from dataclasses import asdict

import pytest

from evals.experiments import jev_target_loot as experiment
from evals.experiments.jev_router_ab import Budget, ExperimentBlocked, _candidate
from services.jev_decision import ChoiceAnswer, DecisionResult, Usage


def _case(case_id: str) -> experiment.ExperimentCase:
    return next(case for case in experiment.load_cases()[0] if case.id == case_id)


def test_corpus_is_frozen_before_any_provider_call() -> None:
    cases, digest = experiment.load_cases()
    assert digest == "sha256:748ab52175a9178aab7d6e14c32c49366abfb77d80eb63641e9377ca7fd89034"
    assert len(cases) == 14
    assert sum(case.measure == "target" for case in cases) == 10
    assert sum(case.measure == "loot_context" for case in cases) == 4
    pre = experiment.preflight()
    assert [row["id"] for row in pre["cases"]] == [case.id for case in cases]
    assert {row["id"]: row["unrepresentable_reason"] for row in pre["cases"]
            if row["unrepresentable_reason"]} == {
                "target.over20": "experiment_target_cap_20",
        "target.missing_id": "visible_actor_without_canonical_id",
    }
    assert experiment._required_calls(pre["cases"]) == 25
    assert next(row for row in pre["cases"] if row["id"] == "target.missing_id")["classifier_eligible"] is False


def test_mismatched_corpus_lock_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "wrong.sha256"
    lock.write_text("sha256:" + "0" * 64 + "\n", encoding="utf-8")
    monkeypatch.setattr(experiment, "CORPUS_LOCK", lock)
    with pytest.raises(ExperimentBlocked, match="hash mismatch"):
        experiment.load_cases()


def test_candidate_drops_expected_and_source_labels() -> None:
    case = _case("target.alias")
    candidate = _candidate(case)
    assert candidate.input == case.input
    assert candidate.input is not case.input
    assert "expected" not in vars(candidate)
    assert "source_case_id" not in vars(candidate)
    assert candidate.description == ""
    assert candidate.tags == ()


def test_only_visible_canonical_scene_ids_become_target_options() -> None:
    secret = experiment._target_options(_case("target.secret").input["state"])
    offscene = experiment._target_options(_case("target.offscene").input["state"])
    alias = experiment._target_options(_case("target.alias").input["state"])
    enemy = experiment._target_options(_case("target.enemy").input["state"])
    assert secret.candidate_ids == offscene.candidate_ids == alias.candidate_ids == ("npc_corvo_rapido",)
    assert "npc_sombra" not in secret.criteria
    assert "Sombra" not in str(secret.criteria)
    assert "npc_velha_magda" not in offscene.criteria
    assert secret.filtered_hidden_count == 1
    assert experiment.canonical_target("Corvo Cinzento", alias) == "npc_corvo_rapido"
    assert enemy.candidate_ids == ("enemy_guarda",)
    assert experiment.canonical_target("Guarda", enemy) == "enemy_guarda"


def test_ambiguous_alias_and_unknown_target_fail_closed() -> None:
    state = {"npcs": {
        "Corvo": {"id": "npc_corvo_rapido", "name": "Corvo", "aliases": ["Velho"], "in_scene": True},
        "Magda": {"id": "npc_velha_magda", "name": "Magda", "aliases": ["Velho"], "in_scene": True},
    }}
    options = experiment._target_options(state)
    assert experiment.canonical_target("Velho", options) == "unknown"
    assert experiment.canonical_target("Nome que não existe", options) == "unknown"
    assert experiment.canonical_target(None, options) == "none"


def test_graph_identity_and_visibility_override_untrusted_runtime_id() -> None:
    canonical = "npc_corvo_rapido"
    state = {"npcs": {"Corvo Rápido": {
        "id": "npc_spoof", "name": "Corvo Rápido", "in_scene": True,
    }}}
    assert experiment._target_options(state).candidate_ids == (canonical,)
    state["world_projection"] = {"entities": {canonical: {"alive": False}}}
    assert experiment._target_options(state).candidate_ids == ()
    state["world_projection"] = {}
    state["combat"] = {"scene": {"positions": {
        canonical: {"hidden_from": ["player"], "ocultacao": "escondido"},
    }}}
    assert experiment._target_options(state).candidate_ids == ()


def test_conflicting_known_graph_id_is_unrepresentable() -> None:
    state = {"npcs": {"Corvo Rápido": {
        "id": "npc_velha_magda", "name": "Corvo Rápido", "in_scene": True,
    }}}
    options = experiment._target_options(state)
    assert options.candidate_ids == ()
    assert options.unrepresentable_reason == "conflicting_canonical_identity"


def test_hidden_enemy_is_not_an_option() -> None:
    state = _case("target.enemy").input["state"]
    state["combat"] = {"scene": {"positions": {
        "enemy_guarda": {"hidden_from": ["player"], "ocultacao": "escondido"},
    }}}
    assert experiment._target_options(state).candidate_ids == ()


def test_hiding_from_another_observer_keeps_enemy_visible_to_player() -> None:
    state = _case("target.enemy").input["state"]
    state["combat"] = {"scene": {"positions": {
        "enemy_guarda": {"hidden_from": ["other_observer"], "ocultacao": "escondido"},
    }}}
    assert experiment._target_options(state).candidate_ids == ("enemy_guarda",)


def test_present_ally_wins_over_offscene_npc_cache_row() -> None:
    state = {"npcs": {"Corvo": {
        "id": "npc_offscene", "name": "Corvo", "in_scene": False,
    }}, "party": [{
        "id": "npc_corvo_rapido", "name": "Corvo", "active": True, "status": "ativo",
    }]}
    assert experiment._target_options(state).candidate_ids == ("npc_corvo_rapido",)


def test_spoof_id_cannot_expose_graph_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(experiment, "resolve_npc_entity_id", lambda *_args: "npc_secret")
    monkeypatch.setattr(experiment.graph_resolver, "get_entity", lambda entity_id: (
        {"type": "npc", "visibility": "secret"} if entity_id == "npc_secret" else None
    ))
    state = {"npcs": {"Sombra": {
        "id": "npc_spoof", "name": "Sombra", "in_scene": True,
    }}}
    options = experiment._target_options(state)
    assert options.candidate_ids == ()
    assert "Sombra" not in str(options.criteria)
    assert options.filtered_hidden_count == 1


def test_classify_auth_failure_blocks_even_after_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def captured(_budget: Budget):
        yield {"attempts": [
            {"provider": "deepseek", "model": "primary", "outcome": "error"},
            {"provider": "groq", "model": "fallback", "outcome": "success"},
        ], "confidence": 0.9, "usage_rows": [], "fatal_sanity_error": True}

    class Adapter:
        def execute(self, _candidate: object):
            return type("Response", (), {"actual": {"target": "none", "route": "npc_actor"}})()

    monkeypatch.setattr(experiment, "_capture_classify", captured)
    monkeypatch.setattr(experiment, "RoutingAdapter", Adapter)
    with pytest.raises(ExperimentBlocked, match="auth/quota/config") as blocked:
        experiment._arm_a(_case("target.zero"), experiment._target_options({}), Budget())
    assert blocked.value.record["attempts"][0]["provider"] == "deepseek"


def test_jev_response_survives_reported_cost_block() -> None:
    class Backend:
        def decide(self, *_args: object, **_kwargs: object) -> DecisionResult:
            return DecisionResult(
                model="jev-test", answers={"loot_context": ChoiceAnswer(
                    type="choice", choice="SHOP", probabilities={"SHOP": 1.0}, confidence=1.0,
                )}, usage=Usage(input_tokens=11, output_tokens=2), correlation_id="test",
                latency_ms=10, cost_usd=2.0,
            )

    with pytest.raises(ExperimentBlocked, match="reported spending") as blocked:
        experiment._arm_b(_case("loot.shop"), None, Backend(),
                          Budget(max_calls=1, max_cost_usd=1), "test-run")
    assert blocked.value.record["choice"] == "SHOP"
    assert blocked.value.record["model"] == "jev-test"
    assert blocked.value.record["usage"]["input_tokens"] == 11


def test_python_gate_current_router_needs_zero_provider_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    @contextmanager
    def captured(_budget: Budget):
        yield {"attempts": [], "confidence": None, "usage_rows": [], "fatal_sanity_error": False}

    class GateAdapter:
        def execute(self, _candidate: object):
            return type("Response", (), {"actual": {
                "route": "storyteller", "target": None, "loot_context": None,
            }})()

    monkeypatch.setattr(experiment, "_capture_classify", captured)
    monkeypatch.setattr(experiment, "RoutingAdapter", GateAdapter)
    budget = Budget()
    case = _case("target.missing_id")
    record = experiment._arm_a(case, experiment._target_options(case.input["state"]), budget)
    assert record["provider"] == "python_gate"
    assert record["choice"] == "none"
    assert budget.calls == 0


def test_resume_rejects_product_code_change(monkeypatch: pytest.MonkeyPatch) -> None:
    def git_probe(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if args[1] == "merge-base":
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "agents/router.py\n", "")

    monkeypatch.setattr(experiment.subprocess, "run", git_probe)
    with pytest.raises(ExperimentBlocked, match="product code changed"):
        experiment._assert_resume_code_drift("prior", "current")


def test_over_twenty_is_reported_without_truncating_candidates() -> None:
    options = experiment._target_options(_case("target.over20").input["state"])
    assert options.unrepresentable_reason == "experiment_target_cap_20"
    assert len(options.candidate_ids) == 21
    assert "enemy_21" in options.candidate_ids
    assert len(options.criteria) == 23  # all 21 targets plus unknown and none


def test_score_keeps_unrepresentable_in_semantic_denominator() -> None:
    cases = [_case("target.one_npc"), _case("target.over20"), _case("loot.shop")]
    raw = {"rows": [
        {"case_id": "target.one_npc", "measure": "target", "status": "paired",
         "candidate_ids": ["npc_corvo_rapido"],
         "a": {"choice": "npc_corvo_rapido", "error": None},
         "b": {"choice": "unknown", "error": None}},
        {"case_id": "target.over20", "measure": "target", "status": "unrepresentable",
         "candidate_ids": ["enemy_21"], "reason": "experiment_target_cap_20"},
        {"case_id": "loot.shop", "measure": "loot_context", "status": "paired",
         "candidate_ids": [],
         "a": {"choice": "SHOP", "error": None},
         "b": {"choice": "SHOP", "error": None}},
    ]}
    summary = experiment.score(raw, cases)
    assert summary["target"]["semantic_count"] == 2
    assert summary["target"]["representable_count"] == 1
    assert summary["target"]["unrepresentable_count"] == 1
    assert summary["target"]["a"]["accuracy_representable"] == 1
    assert summary["target"]["a"]["coverage_adjusted_accuracy"] == 0.5
    assert summary["target"]["b"]["accuracy_representable"] == 0
    assert summary["target"]["invalid_target_count"] == 0
    assert summary["loot_context"]["a"]["accuracy_representable"] == 1


def test_raw_is_durable_before_scoring_and_unrepresentable_never_calls_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    class OfflineBackend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> OfflineBackend:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    calls: list[str] = []

    def arm_a(case: experiment.ExperimentCase, _options: object, budget: Budget) -> dict:
        calls.append("a:" + case.id)
        budget.consume()
        return {"choice": "none", "error": None}

    def arm_b(case: experiment.ExperimentCase, _options: object,
              _backend: object, budget: Budget, _run_id: str) -> dict:
        calls.append("b:" + case.id)
        budget.consume()
        return {"choice": "none", "error": None}

    output_dir = tmp_path / "spec179"
    original_score = experiment.score

    def checked_score(raw: dict, cases: list) -> dict:
        persisted = json.loads((output_dir / "raw.json").read_text(encoding="utf-8"))
        assert persisted["status"] == "complete"
        assert persisted["rows"] == raw["rows"]
        return original_score(raw, cases)

    monkeypatch.setattr(experiment, "JevDecisionBackend", OfflineBackend)
    monkeypatch.setattr(experiment, "_arm_a", arm_a)
    monkeypatch.setattr(experiment, "_arm_b", arm_b)
    monkeypatch.setattr(experiment, "repository_identity", lambda _root: ("sha", "tree", False))
    monkeypatch.setattr(experiment, "score", checked_score)
    raw = experiment.run(output_dir, Budget(max_calls=26, max_cost_usd=0.26))
    assert raw["status"] == "complete"
    assert raw["budget"]["calls"] == 26
    assert "a:target.over20" in calls
    assert "a:target.missing_id" in calls
    assert "b:target.over20" not in calls
    assert "b:target.missing_id" not in calls
    assert all(row.get("fallback", {}).get("fallback_from") == "a"
               for row in raw["rows"] if row["status"] == "unrepresentable")
    assert len(raw["rows"]) == 14
    assert (output_dir / "summary.json").exists()


def test_live_rejects_dirty_checkout_before_backend_or_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(experiment, "repository_identity", lambda _root: ("sha", "tree", True))

    def forbidden_backend(**_kwargs: object):
        raise AssertionError("backend initialized before freeze guard")

    monkeypatch.setattr(experiment, "JevDecisionBackend", forbidden_backend)
    output_dir = tmp_path / "must-not-exist"
    with pytest.raises(ExperimentBlocked, match="must be committed"):
        experiment.run(output_dir, Budget(max_calls=26, max_cost_usd=0.26))
    assert not output_dir.exists()


def test_resume_preserves_prior_raw_and_cumulative_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)
    monkeypatch.delenv("RPG_NO_MOCK", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    cases, digest = experiment.load_cases()
    prepared = experiment.preflight()["cases"]
    rows = []
    for case, pre in zip(cases[:10], prepared[:10], strict=True):
        row = {"case_id": case.id, "measure": case.measure,
               "candidate_ids": pre["candidate_ids"],
               "filtered_hidden_count": pre["filtered_hidden_count"]}
        if case.id == "target.missing_id":
            row.update(status="unrepresentable", reason=pre["unrepresentable_reason"],
                       a={"error": "CLASSIFY has no real decision", "attempts": []})
        elif case.id == "target.over20":
            row.update(status="unrepresentable", reason=pre["unrepresentable_reason"],
                       a={"choice": "unknown", "attempts": [{"outcome": "success"}], "error": None},
                       fallback={"choice": "unknown", "fallback_from": "a"})
        else:
            row.update(status="paired",
                       a={"choice": "none", "attempts": [{"outcome": "success"}], "error": None},
                       b={"choice": "none", "attempts": [{"outcome": "success"}], "error": None})
        rows.append(row)
    prior = {"run_id": "prior", "product_sha": "prior-sha", "product_tree_hash": "prior-tree",
             "product_dirty": False,
             "status": "blocked-by-provider", "blocker": "CLASSIFY gate misread",
             "corpus_hash": digest, "case_order": [case.id for case in cases],
             "budget": asdict(Budget(max_calls=40, max_cost_usd=0.40, calls=17)), "rows": rows}
    source_path = tmp_path / "prior-raw.json"
    source_path.write_text(json.dumps(prior), encoding="utf-8")
    original_bytes = source_path.read_bytes()
    source_hash = experiment.sha256_file(source_path)
    monkeypatch.setattr(experiment, "RECOVERY_RAW_SHA256", source_hash)
    monkeypatch.setattr(experiment, "_assert_resume_code_drift", lambda *_args: None)
    calls: list[str] = []

    class OfflineBackend:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> OfflineBackend:
            return self

        def __exit__(self, *_args: object) -> None:
            pass

    def arm_a(case: experiment.ExperimentCase, _options: object, budget: Budget) -> dict:
        calls.append("a:" + case.id)
        if case.id != "target.missing_id":
            budget.consume()
        return {"choice": "none", "provider": "python_gate" if case.id == "target.missing_id" else "test",
                "attempts": [], "error": None}

    def arm_b(case: experiment.ExperimentCase, _options: object,
              _backend: object, budget: Budget, _run_id: str) -> dict:
        calls.append("b:" + case.id)
        budget.consume()
        return {"choice": "none", "attempts": [], "error": None}

    monkeypatch.setattr(experiment, "JevDecisionBackend", OfflineBackend)
    monkeypatch.setattr(experiment, "_arm_a", arm_a)
    monkeypatch.setattr(experiment, "_arm_b", arm_b)
    monkeypatch.setattr(experiment, "repository_identity", lambda _root: ("new-sha", "new-tree", False))
    output_dir = tmp_path / "resumed"
    with pytest.raises(ExperimentBlocked, match="raw hash differs"):
        experiment.run(output_dir, Budget(max_calls=40, max_cost_usd=0.40),
                       resume_from=source_path, resume_sha256="sha256:" + "0" * 64)
    assert not output_dir.exists()
    raw = experiment.run(output_dir, Budget(max_calls=40, max_cost_usd=0.40),
                         resume_from=source_path, resume_sha256=source_hash)
    assert raw["status"] == "complete"
    assert raw["budget"]["calls"] == 25
    assert raw["resumed_from"]["calls_before_resume"] == 17
    assert raw["rows"][9]["a_before_resume"]["error"] == "CLASSIFY has no real decision"
    assert raw["rows"][9]["a"]["provider"] == "python_gate"
    assert calls == ["a:target.missing_id",
                     "a:loot.treasure", "b:loot.treasure", "a:loot.shop", "b:loot.shop",
                     "a:loot.craft", "b:loot.craft", "a:loot.none", "b:loot.none"]
    assert source_path.read_bytes() == original_bytes
    assert (output_dir / "summary.json").exists()
