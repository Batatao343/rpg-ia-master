"""SPEC-360 R13, R19, R24: presenca (nasce, expira, caps, determinismo, save antigo)."""

from __future__ import annotations

import pytest

from services import fauna, world_engine

LAMA = "na_anel_lama"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def _ctx(day: int, sim: dict, gid: str = "g1", loc: str = LAMA):
    world = {"current_location_id": loc, "world_clock": {"day": day, "period": "Manhã"}}
    return world_engine.DayContext(
        game_id=gid,
        day=day,
        sim=sim,
        projection={},
        world=world,
        factions=[],
        rng=world_engine.day_rng(gid, day, "x"),
        state={"game_id": gid, "world": world, "world_sim": sim},
    )


def _run(days: int, gid: str = "g1") -> dict:
    sim: dict = {}
    for d in range(1, days + 1):
        fauna.day_hook(_ctx(d, sim, gid))
    return sim


def _active(sim: dict, day: int) -> list[dict]:
    return [p for p in sim["fauna"]["presencas"] if fauna._active(p, day)]


def test_hook_registrado_antes_dos_rumores():
    hooks = {name: (stage, order) for name, stage, order, _fn in world_engine._HOOKS}
    assert hooks["fauna"] == ("post", 15)
    assert hooks["rumors"][1] > 15


def test_day_hook_nasce_no_maximo_por_regiao(on):
    sim = _run(25)
    cap = fauna.const("MAX_PRESENCAS_REGIAO")
    act = _active(sim, 25)
    assert 1 <= len(act) <= cap
    assert all(p["region_id"] == "nova_arcadia" for p in act)
    assert all(p["origem"] == "dia" for p in sim["fauna"]["presencas"])
    for p in act:
        assert set(p["locais"]) <= set(fauna.effective_territory(p["creature_id"]))
        assert len(p["locais"]) <= fauna.const("MAX_LOCAIS")


def test_um_por_dia(on):
    sim: dict = {}
    for d in range(1, 6):
        before = len(((sim.get("fauna") or {}).get("presencas")) or [])
        fauna.day_hook(_ctx(d, sim))
        assert len(sim["fauna"]["presencas"]) - before <= 1


def test_nunca_boss(on):
    import gamedata
    from encounter_budget import is_boss

    sim = _run(60)
    assert not any(is_boss(gamedata.BESTIARY[p["creature_id"]]) for p in sim["fauna"]["presencas"])


def test_ttl_e_dispersa(on):
    sim = _run(3)
    first = sim["fauna"]["presencas"][0]
    lo, hi = fauna.entry(first["creature_id"])["ecologia"]["permanencia"]
    assert lo - 1 <= first["expires_day"] - first["born_day"] <= hi - 1
    for d in range(4, first["expires_day"] + 3):
        fauna.day_hook(_ctx(d, sim))
    row = next(p for p in sim["fauna"]["presencas"] if p["pid"] == first["pid"])
    assert row["status"] == "dispersa"
    assert fauna.presence_at(sim, LAMA, first["expires_day"] + 1) is None or (
        fauna.presence_at(sim, LAMA, first["expires_day"] + 1)["pid"] != first["pid"]
    )


def test_determinismo_day_rng(on):
    assert _run(20, "abc") == _run(20, "abc")
    assert _run(20, "abc") != _run(20, "xyz")


def test_caps(on):
    rows = [
        {
            "pid": f"p{i}",
            "creature_id": "mon_porca_da_queda",
            "region_id": "nova_arcadia",
            "locais": [LAMA],
            "born_day": i,
            "expires_day": i if i < 10 else 99,
            "sinais_mostrados": [],
            "origem": "dia",
            "status": "dispersa" if i < 10 else "ativa",
        }
        for i in range(30)
    ]
    norm = fauna.normalize_fauna_sim({"presencas": rows, "carcacas": []})
    assert len(norm["presencas"]) == fauna.const("MAX_PRESENCAS")
    assert sum(p["status"] == "ativa" for p in norm["presencas"]) == min(20, 12)


def test_normalize_save_antigo():
    assert fauna.normalize_fauna_sim(None) == {"v": 1, "presencas": [], "carcacas": []}
    assert fauna.normalize_fauna_sim({}) == {"v": 1, "presencas": [], "carcacas": []}


def test_flags_off_nao_nasce(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "off")
    sim = _run(10)
    assert "fauna" not in sim


def test_sinais_sem_motor_vale_off(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "off")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    assert fauna.sinais_mode() == "off"
