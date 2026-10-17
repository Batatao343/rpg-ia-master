"""SPEC-212 Etapa 1: o mapa de nomes da spec reproduz o veredito da regua (paridade)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services import gameplay_oracles as oracles

DATASET = Path(__file__).resolve().parents[1] / "evals/datasets/regression/gameplay_gate.jsonl"
BY_OPERATION = {
    "turns": oracles.no_duplicate_turns, "secrets": oracles.no_unrevealed_secret,
    "xp": oracles.xp_not_in_prose, "latency": oracles.latency_present,
    "speaker": oracles.speaker_matches, "roster": oracles.roster_stable,
}


def _cases():
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        if case["input"]["operation"] in BY_OPERATION:
            yield pytest.param(case, id=case["id"])


@pytest.mark.parametrize("case", list(_cases()))
def test_oracle_parity_with_ruler_dataset(case):
    operation = case["input"]["operation"]
    found = BY_OPERATION[operation](case["input"]["trace"])
    expected = case["expected"]["problem_classes"]
    assert bool(found) == bool(expected), (case["id"], found, expected)


def test_post_transport_null_server_ttfmc_ok():
    turn = {"transport": "post",
            "client": {"ack_ms": 1, "first_phase_ms": None, "ttfmc_ms": 5, "ttlt_ms": 6, "state_ms": 7},
            "server": {"transport": "post", "pseudo_streaming": True, "ack_server_ms": 1,
                       "ttfmc_server_ms": None, "ttlt_server_ms": None,
                       "phase_ms": {p: 1 for p in ("router", "context", "narrator", "archivist", "persistence")}}}
    assert oracles.latency_present({"turns": [turn]}) == []


def test_stream_null_server_marks_fail():
    turn = {"transport": "stream",
            "client": {"ack_ms": 1, "first_phase_ms": 2, "ttfmc_ms": 5, "ttlt_ms": 6, "state_ms": 7},
            "server": {"transport": "stream", "pseudo_streaming": True, "ack_server_ms": 1,
                       "ttfmc_server_ms": None, "ttlt_server_ms": None,
                       "phase_ms": {p: 1 for p in ("router", "context", "narrator", "archivist", "persistence")}}}
    assert oracles.latency_present({"turns": [turn]}) == ["latency:null_server_stream"]
