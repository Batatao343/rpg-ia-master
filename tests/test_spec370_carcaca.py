"""SPEC-370 R13: a carcaça da fauna sai do `_combat_node` (não só de `record_kill`)."""

from __future__ import annotations

import random

import pytest
from langchain_core.messages import HumanMessage

import agents.combat as combat
from tests.fixtures import spec346_smoke as smoke
from tests.test_spec346_board_no_llm import _after_open, _attack_decl, _open
from tests.test_spec346_outcome import _force_victory, _install

CREATURE = "mon_porca_da_queda"


@pytest.fixture(autouse=True)
def _board_on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(11)


def _kill(monkeypatch) -> tuple[dict, dict]:
    state, res = _open(monkeypatch)
    _install(monkeypatch, text=smoke.GOOD_SUMMARY)
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo a carta")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    _force_victory(monkeypatch, nonlethal=False)
    # o roster do encontro só aceita o goblin da cena; a identidade vira a da fauna aqui
    monkeypatch.setattr(combat.disc, "normalize_bestiary_id", lambda _e: CREATURE)
    return nxt, combat._combat_node(nxt)


def _carcasses(out: dict) -> list[dict]:
    return list(((out.get("world_sim") or {}).get("fauna") or {}).get("carcacas") or [])


def test_carcaca_pelo_combat_node_on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    nxt, out = _kill(monkeypatch)
    loc = nxt["world"]["current_location_id"]
    rows = _carcasses(out)
    assert rows and rows[0]["creature_id"] == CREATURE and rows[0]["loc"] == loc
    assert set(rows[0]) == {"loc", "day", "creature_id"}


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_carcaca_nao_grava_sem_on(monkeypatch, mode):
    monkeypatch.setenv("RPG_FAUNA", mode)
    _nxt, out = _kill(monkeypatch)
    assert _carcasses(out) == []
