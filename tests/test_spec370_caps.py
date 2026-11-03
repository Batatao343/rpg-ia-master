"""SPEC-370 R9/R10: cap por regiao proporcional aos nos e cap global sem descarte da recem-nascida."""

from __future__ import annotations

import pytest

from services import fauna, world_engine

NA_LOC = "na_anel_lama"
CRIATURA = "mon_porca_da_queda"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setitem(fauna._config(), "P_PRESENCA", 1.0)  # nasce sempre que ha vaga


def _row(i: int, region: str, *, day: int = 1, sinais=(), status: str = "ativa") -> dict:
    return {
        "pid": f"p{i:02d}",
        "creature_id": CRIATURA,
        "region_id": region,
        "locais": [NA_LOC],
        "born_day": day,
        "expires_day": 99,
        "sinais_mostrados": list(sinais),
        "origem": "dia",
        "status": status,
    }


def _ctx(day: int, sim: dict, loc: str = NA_LOC):
    world = {"current_location_id": loc, "world_clock": {"day": day, "period": "Noite"}}
    return world_engine.DayContext(
        game_id="g1",
        day=day,
        sim=sim,
        projection={},
        world=world,
        factions=[],
        rng=world_engine.day_rng("g1", day, "x"),
        state={"game_id": "g1", "world": world, "world_sim": sim},
    )


def test_region_cap_ophidia_1():
    assert fauna.region_cap("ophidia") == 1


def test_region_cap_na_4():
    assert fauna.region_cap("nova_arcadia") == 4
    assert fauna.region_cap("skallgard") == 3  # 3 nos raiz < 4
    assert fauna.region_cap("regiao_inexistente") == fauna.const("MAX_PRESENCAS_REGIAO")


def test_cap_global_preserva_recem_nascida(on):
    others = [_row(i, "skallgard", day=1 + i) for i in range(12)]
    sim = {"fauna": {"v": 1, "presencas": others, "carcacas": []}}
    fauna.day_hook(_ctx(20, sim))
    rows = sim["fauna"]["presencas"]
    assert len(rows) <= fauna.const("MAX_PRESENCAS")
    novas = [p for p in rows if p["region_id"] == "nova_arcadia" and p["born_day"] == 20]
    assert len(novas) == 1, "a recem-nascida sobrevive ao cap"
    assert "p00" not in {p["pid"] for p in rows}, "saiu a ativa mais antiga de outra regiao"


def test_cap_global_nunca_descarta_presenca_lida():
    rows = [_row(i, "nova_arcadia", sinais=["rastro"]) for i in range(12)]
    fauna_sim = {"v": 1, "presencas": list(rows), "carcacas": []}
    ok = fauna._make_room(fauna_sim, "nova_arcadia", "nova_arcadia", ["nova_arcadia"], 5)
    assert ok is False
    assert len(fauna_sim["presencas"]) == 12


def test_cap_global_nao_tira_a_regiao_mais_frequentada():
    rows = [_row(i, "skallgard", day=i) for i in range(12)]
    fauna_sim = {"v": 1, "presencas": list(rows), "carcacas": []}
    assert not fauna._make_room(fauna_sim, "nova_arcadia", "nova_arcadia", ["skallgard"], 5)
    assert len(fauna_sim["presencas"]) == 12


def test_cap_global_descarta_nao_ativa_primeiro():
    rows = [_row(i, "skallgard", day=10 + i) for i in range(11)]
    rows.append(_row(11, "skallgard", day=1, status="dispersa"))
    fauna_sim = {"v": 1, "presencas": rows, "carcacas": []}
    assert fauna._make_room(fauna_sim, "nova_arcadia", "nova_arcadia", [], 20)
    assert len(fauna_sim["presencas"]) == 11
    assert all(p["status"] == "ativa" for p in fauna_sim["presencas"])


def test_cap_global_sem_log_fantasma(on, monkeypatch):
    rows = [_row(i, "skallgard") for i in range(12)]
    sim = {
        "fauna": {"v": 1, "presencas": rows, "carcacas": []},
        "region_presence": {"skallgard": 20},  # a mais frequentada: ninguem sai
    }
    logs: list[str] = []
    monkeypatch.setattr(fauna, "_log", lambda name, **kw: logs.append(name))
    fauna.day_hook(_ctx(20, sim))
    assert "presenca_nasce" not in logs
    assert not [p for p in sim["fauna"]["presencas"] if p["region_id"] == "nova_arcadia"]
