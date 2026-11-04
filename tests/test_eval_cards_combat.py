"""Deterministic card-combat eval contracts (SPEC-380 R2.8)."""

from __future__ import annotations

import os
import random
from collections import Counter
from pathlib import Path

import pytest

from evals.core.adapters import AdapterCase, AdapterError, default_registry
from evals.core.governance import load_cases
from evals.core.runner import run_eval
from evals.evaluators.projection import ProjectionEvaluator

ROOT = Path(__file__).resolve().parents[1]
DATASET = "datasets/regression/cards_combat.jsonl"
FLAGS = ("RPG_ENEMY_INTENT", "RPG_CARD_DECK", "RPG_ENEMY_DECKS", "RPG_RUNTIME_PROFILE")
TEXT_KEYS = {"logs", "log", "narracao", "sinal", "texto", "scene_logs"}


def _cases():
    return load_cases(ROOT / "evals" / DATASET)


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def test_corpus_shape_follows_r2() -> None:
    cases = _cases()
    assert len(cases) >= 16
    assert {case.suite for case in cases} == {"cards_combat"}
    assert {case.oracle for case in cases} == {"projection"}
    tags = Counter(tag for case in cases for tag in case.tags)
    assert tags["known-bad"] >= 2
    assert tags["dano"] >= 6 and tags["condicao"] >= 4
    assert tags["fim"] >= 3 and tags["pressagio"] >= 3
    assert tags["custo"] <= 4
    for case in cases:
        assert case.description and case.created_from, case.id
        assert (ROOT / case.created_from).is_file(), case.id
        assert set(case.input["flags"]) == set(FLAGS), case.id
        assert not (_keys(case.expected) & TEXT_KEYS), case.id
        leaves = {part for path in case.input["projection"] for part in path.split(".")}
        assert not (leaves & TEXT_KEYS), case.id


def test_corpus_passes_fully() -> None:
    result = run_eval(ROOT, datasets=[DATASET], run_id="cards-combat")

    assert result.error_case_ids == []
    assert result.passed is True
    assert len(result.results) == len(_cases())
    assert result.metric_values == {"state_transition_pass_rate": 1.0}


def _probe(**input_) -> AdapterCase:
    return AdapterCase(
        id="probe",
        suite="cards_combat",
        description="probe",
        fixture=None,
        input=input_,
        tags=(),
        source="synthetic",
        created_from=None,
    )


def test_adapter_reports_a_regression_instead_of_hiding_it() -> None:
    case = next(c for c in _cases() if c.input["operation"] == "damage")
    actual = default_registry().resolve("cards_combat").execute(_probe(**case.input)).actual
    tampered = {
        key: (value + 1 if isinstance(value, int) else value) for key, value in actual.items()
    }
    assert tampered != actual
    result = ProjectionEvaluator().evaluate(
        case, tampered, product_sha="x", dataset_hash="sha256:" + "0" * 64, seed=7
    )
    assert result.passed is False


def test_adapter_fails_closed_on_unknown_operation() -> None:
    adapter = default_registry().resolve("cards_combat")
    flags = dict.fromkeys(FLAGS, "off")
    with pytest.raises(AdapterError):
        adapter.execute(_probe(operation="nope", flags=flags, projection=["x"]))


def test_adapter_recusa_caso_sem_flags() -> None:
    adapter = default_registry().resolve("cards_combat")
    case = next(c for c in _cases() if c.input["operation"] == "folego")
    partial = {k: v for k, v in case.input["flags"].items() if k != "RPG_ENEMY_DECKS"}
    with pytest.raises(AdapterError, match="RPG_ENEMY_DECKS"):
        adapter.execute(_probe(**{**case.input, "flags": partial}))
    with pytest.raises(AdapterError):
        adapter.execute(_probe(**{k: v for k, v in case.input.items() if k != "flags"}))


def test_adapter_restaura_env_e_random_global(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RPG_ENEMY_INTENT", "shadow")
    monkeypatch.delenv("RPG_CARD_DECK", raising=False)
    random.seed(99)
    before = random.getstate()
    case = next(c for c in _cases() if c.input["operation"] == "round")
    default_registry().resolve("cards_combat").execute(_probe(**case.input))
    assert os.environ["RPG_ENEMY_INTENT"] == "shadow"
    assert "RPG_CARD_DECK" not in os.environ
    assert random.getstate() == before


def test_adapter_recusa_caminho_de_projecao_inexistente() -> None:
    case = next(c for c in _cases() if c.input["operation"] == "folego")
    with pytest.raises(AdapterError, match="projection"):
        default_registry().resolve("cards_combat").execute(
            _probe(**{**case.input, "projection": ["nao.existe"]})
        )
