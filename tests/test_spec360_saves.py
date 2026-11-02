"""SPEC-360 R23-R24: round-trip de `world_sim.fauna`, save antigo e `sinais_vistos`."""

from __future__ import annotations

import persistence
from services import discovery as disc
from services import fauna
from tests.test_spec360_sinais import presence, sim_with, state_at


def _roundtrip(state: dict) -> dict:
    state = {**state, "game_id": "3f6c1d2e-0a4b-4c5d-8e9f-360360360360"}
    assert persistence.save_game_state(state)
    return persistence.load_game_state(persistence.save_path(state["game_id"]))


def test_roundtrip_fauna(tmp_path):
    sim = sim_with(presence(shown=("rastro",)))
    sim["fauna"]["carcacas"] = [{"loc": "na_anel_lama", "day": 4, "creature_id": "mon_arame_vivo"}]
    st = state_at(sim={**sim, "version": 1, "extra": {"k": 1}})
    loaded = _roundtrip(st)
    assert loaded["world_sim"]["fauna"] == fauna.normalize_fauna_sim(sim["fauna"])
    assert loaded["world_sim"]["extra"] == {"k": 1}


def test_save_antigo_sem_chave():
    st = state_at(sim={"version": 1, "rumors": []})
    loaded = _roundtrip(st)
    assert "fauna" not in loaded["world_sim"]
    assert fauna.normalize_fauna_sim(loaded["world_sim"].get("fauna")) == {
        "v": 1,
        "presencas": [],
        "carcacas": [],
    }


def test_presenca_de_criatura_removida_descartada(monkeypatch):
    import observability.telemetry as tel

    seen = []
    monkeypatch.setattr(tel, "log_fallback", lambda *a, **k: seen.append(a))
    sim = sim_with(presence(), presence(cid="mon_que_nao_existe", pid="pidsumiu0001"))
    loaded = _roundtrip(state_at(sim=sim))
    pids = [p["pid"] for p in loaded["world_sim"]["fauna"]["presencas"]]
    assert pids == ["pidarame0001"]
    assert any(a[:2] == ("fauna", "presenca_sem_criatura") for a in seen)


def test_sinais_vistos_no_bestiary_knowledge():
    bk = disc.record_rumor({}, "mon_arame_vivo", 3)
    bk = disc.record_sinais(bk, "mon_arame_vivo", ["rastro", "som"], 5)
    bk = disc.record_sinais(bk, "mon_arame_vivo", ["som", "cheiro"], 6)
    row = bk["mon_arame_vivo"]
    assert row["sinais_vistos"] == ["rastro", "som", "cheiro"]
    assert row["seen"] == 1 and row["last_update_turn"] == 3  # contador de caca intocado
    assert disc.record_sinais(bk, "mon_arame_vivo", [], 7) == bk
