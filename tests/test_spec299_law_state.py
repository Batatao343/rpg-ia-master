"""SPEC-299 etapa 2 — estado ``law_state``, flag ``RPG_LAW`` e save (aditivo, sem bump)."""

from __future__ import annotations

import json
import os

import persistence
from services import law
from tests.spec299_helpers import base_state, commit

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "save_v8_pre_spec202.json")


def _fixture() -> dict:
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


def test_normalize_law_empty_on_old_save():
    state = persistence._raw_to_state(_fixture())
    assert "law_state" not in state  # save antigo carrega sem a chave
    empty = law.normalize_law(state.get("law_state"))
    assert empty["crimes"] == [] and empty["wanted"] == {} and empty["confrontation"] is None


def test_normalize_law_garbage_is_safe():
    for raw in (None, 5, "x", [], {"crimes": "x", "wanted": 3, "served": [1, None]}):
        out = law.normalize_law(raw)
        assert out["crimes"] == [] and out["wanted"] == {} and out["served"] == []


def test_roundtrip_preserves_law_state(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    state = persistence._raw_to_state(_fixture())
    st, rec, why = commit(base_state(game_id=state["game_id"]), "furto")
    assert rec is not None, why
    state["law_state"] = st["law_state"]
    first = json.dumps(
        persistence._state_to_save_data(state, state["game_id"]), sort_keys=True, default=str
    )
    loaded = persistence._raw_to_state(json.loads(first))
    assert loaded["law_state"] == law.normalize_law(state["law_state"])
    second = json.dumps(
        persistence._state_to_save_data(loaded, loaded["game_id"]), sort_keys=True, default=str
    )
    assert first == second


def test_caps_fifo():
    rows = [{"crime_id": f"c{i}", "status": "reported"} for i in range(150)]
    reports = [{"report_id": f"r{i}", "crime_id": "c"} for i in range(150)]
    served = [
        {"jurisdiction_id": "j", "mode": "fine", "turn": i, "crime_ids": []} for i in range(40)
    ]
    out = law.normalize_law({"crimes": rows, "reports": reports, "served": served})
    assert len(out["crimes"]) == law.MAX_CRIMES and out["crimes"][-1]["crime_id"] == "c149"
    assert len(out["reports"]) == law.MAX_REPORTS
    assert len(out["served"]) == law.MAX_SERVED and out["served"][-1]["turn"] == 39
    w = law.normalize_law({"wanted": {"j": {"signals_shown": [str(i) for i in range(60)]}}})
    assert len(w["wanted"]["j"]["signals_shown"]) == law.MAX_SIGNALS


def test_mode_off_writes_nothing(monkeypatch):
    monkeypatch.delenv("RPG_LAW", raising=False)
    assert law.mode() == "off"
    upd, rec, why = law.register_crime(
        base_state(), {"crime_type": "furto", "victim_ref": "local", "source": "engine"}
    )
    assert (upd, rec, why) == ({}, None, "off")
    assert law.turn_updates(base_state()) == {}
    assert (
        law.apply_claims(base_state(), [{"crime_type": "furto"}], player_text="roubo a bolsa") == {}
    )
    assert law.signals_for(base_state()) == []
    assert law.scene_block(base_state()) == ("", {})
    # sem law_state o save não ganha chave nova
    data = persistence._state_to_save_data(base_state(), "g")
    assert "law_state" not in data


def test_invalid_mode_value_is_off(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "talvez")
    assert law.mode() == "off"


def test_no_schema_version_bump():
    assert persistence.SCHEMA_VERSION == 8
