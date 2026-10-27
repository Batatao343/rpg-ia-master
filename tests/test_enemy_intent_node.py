"""SPEC-329: Presságio pelo nó de combate real, com save/load entre rodadas e a view da API."""

from __future__ import annotations

import json
import random

import agents.combat as combat
import api
import persistence
from tests.test_encounter_identity_repro import _BANDIT, _install_llm, _start_state
from tests.test_encounter_lifecycle_reload import _decl, _merge, _reload


def _start(monkeypatch):
    random.seed(9)
    _install_llm(monkeypatch)
    return _decl(
        _start_state(
            combat_encounter_hint={"enemy_id": _BANDIT, "reason": "random", "hint": "Bandido"},
            world={**_start_state()["world"], "danger_level": 1},
            continuity={"session_action_count": 4, "timeline_epoch": 0},
        )
    )


def _rounds(monkeypatch, n):
    state = _start(monkeypatch)
    metas = []
    for _ in range(n):
        out = combat.combat_node(state)
        state = _reload(_merge(state, out))
        metas.append(json.loads(json.dumps(state["combat"], default=str)))
        if not state["combat"].get("active"):
            break
        _decl(state)
    return state, metas


def test_on_roundtrip_through_node_and_save(monkeypatch):
    from services import conflict_orchestrator as orch

    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    seen: list[dict] = []
    real = orch.run_round

    def spy(*a, **k):
        out = real(*a, **k)
        seen.append({"pressagios": k.get("pressagios"), "out": out})
        return out

    monkeypatch.setattr(orch, "run_round", spy)
    state, metas = _rounds(monkeypatch, 3)
    frozen = [(i, m) for i, m in enumerate(metas) if m.get("pressagios")]
    assert frozen, "nenhuma rodada congelou presságio"
    i, meta = frozen[0]
    assert i + 1 < len(seen), "sem rodada seguinte para consumir"
    # a rodada seguinte recebeu, após save/load, exatamente o presságio congelado
    assert seen[i + 1]["pressagios"] == meta["pressagios"]
    nxt = seen[i + 1]["out"]
    assert nxt.get("pressagios_cumpridos") or nxt.get("pressagios_frustrados")
    # visão pública: sem declaração nem carta_id; bloco da API só com a flag `on`
    row = meta["pressagios_publicos"][0]
    assert not {"declaration", "carta_id"} & set(row)
    view = api._combat_block({"combat": meta, "enemies": [], "player": {}})
    assert view["pressagios_publicos"] == meta["pressagios_publicos"]
    monkeypatch.delenv("RPG_ENEMY_INTENT")
    assert "pressagios_publicos" not in api._combat_block(
        {"combat": meta, "enemies": [], "player": {}}
    )


def test_off_save_has_no_new_keys(monkeypatch):
    monkeypatch.delenv("RPG_ENEMY_INTENT", raising=False)
    state, metas = _rounds(monkeypatch, 3)
    for m in metas:
        assert "pressagios" not in m and "pressagios_publicos" not in m
    saved = json.dumps(persistence._state_to_save_data(state, state["game_id"]), default=str)
    assert "pressagios" not in saved
