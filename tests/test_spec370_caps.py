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


# ----------------------------------------------------------------- P2-4 / P2-5 (Sol)


def _state(sim: dict) -> dict:
    return {
        "game_id": "g1",
        "world": {"current_location_id": "ophidia", "world_clock": {"day": 5}},
        "world_sim": sim,
    }


def _cids(region: str, ante: str = "cedo") -> list[str]:
    return [
        c
        for c, e in sorted(fauna.load().items())
        if e["regiao"] == region and (e.get("sinais") or {}).get("antecedencia") == ante
    ]


def test_conversao_respeita_teto_da_regiao(monkeypatch):
    """P2-5: Ophidia (teto 1) com uma presenca nao lida: a conversao a substitui, nunca vira 2."""
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    a, b = _cids("ophidia")[:2]
    old = {**_row(0, "ophidia"), "creature_id": a, "locais": ["ophidia"], "expires_day": 99}
    sim = {"fauna": {"v": 1, "presencas": [old], "carcacas": []}}
    note, upd = fauna.convert_to_signal(_state(sim), fauna.entry(b), "ophidia", 5)
    assert note
    rows = [p for p in upd["world_sim"]["fauna"]["presencas"] if p["status"] == "ativa"]
    assert len(rows) == 1 and rows[0]["creature_id"] == b


def test_conversao_sem_vaga_nao_cria_nem_sinal_orfao(monkeypatch):
    """P2-4/P2-5: a unica presenca da regiao ja foi lida: nao se descarta, nao ha sinal solto."""
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    a, b = _cids("ophidia")[:2]
    lida = {
        **_row(0, "ophidia", sinais=["rastro"]),
        "creature_id": a,
        "locais": ["ophidia"],
    }
    sim = {"fauna": {"v": 1, "presencas": [lida], "carcacas": []}}
    note, upd = fauna.convert_to_signal(_state(sim), fauna.entry(b), "ophidia", 5)
    assert note == "" and upd == {}


def test_add_presence_sem_vaga_nao_remove_nada(monkeypatch):
    """P2-10 (Sol): o teto da regiao libera vaga tirando uma nao lida, mas o cap global nao
    tem o que tirar: nao nasce e o `sim` devolvido e o original (nada removido sem nascer)."""
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")
    monkeypatch.setitem(fauna._config(), "MAX_PRESENCAS", 3)
    na = _cids("nova_arcadia")
    rows = [_row(i, "nova_arcadia", sinais=["rastro"]) for i in range(3)]
    rows.append({**_row(3, "nova_arcadia"), "locais": [NA_LOC]})  # a unica nao lida
    sim = {"fauna": {"v": 1, "presencas": rows, "carcacas": []}}
    state = {"game_id": "g1", "world": {"current_location_id": NA_LOC}, "world_sim": sim}
    new_sim, pres = fauna._add_presence(state, fauna.entry(na[0]), NA_LOC, 5, "conversao", "marca")
    assert pres is None
    assert new_sim is sim
    assert {p["pid"] for p in sim["fauna"]["presencas"]} == {"p00", "p01", "p02", "p03"}
