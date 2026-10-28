"""SPEC-345 R2/R3: quem saiu do combate sai da view (o estado não muda)."""

from __future__ import annotations

from copy import deepcopy

import api
from tests.test_combat_simulator import _request


def _state() -> dict:
    state = api._build_combat_simulator_state(_request(quantity=2))
    return state


def _ids(state):
    return [e["id"] for e in state["enemies"]]


def _positions(block):
    return {p["participant_id"]: p for p in block["scene"]["positions"]}


def test_inimigo_morto_sai_das_posicoes_e_engajamentos():
    state = _state()
    dead_id, alive_id = _ids(state)
    state["combat"]["scene"]["positions"]["player"]["engaged_with"] = [dead_id, alive_id]
    state["enemies"][0].update(dead=True, status="morto")
    block = api._combat_block(state)
    pos = _positions(block)
    assert dead_id not in pos and alive_id in pos
    for row in pos.values():
        assert dead_id not in row["engaged_with"]
        assert state["enemies"][0]["name"] not in row["engaged_names"]
    # manifesto congelado (SPEC-203) segue com todos
    ids = {p["participant_id"] for p in block["encounter_view"].get("participants", [])}
    assert not ids or {dead_id, alive_id} <= ids


def test_inimigo_vitalidade_zero_continua_no_combate():
    state = _state()
    first, _ = _ids(state)
    state["enemies"][0]["vitalidade"] = 0
    block = api._combat_block(state)
    assert first in _positions(block)
    assert any(e["id"] == first for e in block["enemies"])


def test_pressagio_sem_ator_morto(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    state = _state()
    dead_id, alive_id = _ids(state)
    state["combat"]["pressagios_publicos"] = [
        {"actor_id": dead_id, "x": 1},
        {"actor_id": alive_id, "x": 2},
    ]
    state["enemies"][0].update(dead=True, status="morto")
    view = api._combat_block(state)["pressagios_publicos"]
    assert [row["actor_id"] for row in view] == [alive_id]
    assert len(state["combat"]["pressagios_publicos"]) == 2


def test_estado_nao_muda():
    state = _state()
    state["enemies"][0].update(dead=True, status="morto")
    before = deepcopy(state)
    api._combat_block(state)
    assert state == before
    assert _ids(state)[0] in state["combat"]["scene"]["positions"]
