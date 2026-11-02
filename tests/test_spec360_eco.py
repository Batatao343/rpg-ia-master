"""SPEC-360 R8-R12: motor de ecologia (`RPG_FAUNA`)."""

from __future__ import annotations

import random

import pytest

import gamedata
import world_utils as wu
from services import fauna

LAMA, FERRO, DOURADO = "na_anel_lama", "na_anel_ferro", "na_anel_dourado"


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("RPG_FAUNA", "on")
    monkeypatch.setenv("RPG_FAUNA_SINAIS", "on")


def _ctx(loc=LAMA, period="Noite", season=None, bk=None, **kw) -> fauna.EcoCtx:
    return fauna.EcoCtx(
        location_id=loc,
        region_id="nova_arcadia",
        period=period,
        season=season,
        bestiary_knowledge=bk or {},
        turn=100,
        **kw,
    )


def _world(loc=LAMA, period="Noite", **extra) -> dict:
    return {"current_location_id": loc, "world_clock": {"day": 5, "period": period}, **extra}


def _share(cid, loc=LAMA, period="Noite", bk=None, world_extra=None, sim=None) -> float:
    rows = wu.encounter_distribution(
        gamedata.get_location(loc),
        3,
        100,
        bestiary_knowledge=bk or {},
        projection={},
        world=_world(loc, period, **(world_extra or {})),
        world_sim=sim or {},
    )
    total = sum(w for _e, w in rows)
    return sum(w for e, w in rows if e["id"] == cid) / total


def test_fator_horario():
    e = fauna.entry("mon_porca_da_queda")  # Anoitecer, Noite
    assert fauna.eco_multiplier(e, _ctx(period="Noite"))[0] == 1.0
    f, why = fauna.eco_multiplier(e, _ctx(period="Manhã"))
    assert f == pytest.approx(fauna.const("HORARIO_FORA")) and "horario" in why


def test_fator_estacao_substitui_calendario(on, monkeypatch):
    from services import world_calendar

    e = fauna.entry("mon_arame_vivo")
    assert fauna.eco_multiplier(e, _ctx(season="verao"))[0] == pytest.approx(0.7)
    # calendario dobraria a criatura; com fauna a ficha substitui (sem dupla contagem)
    monkeypatch.setattr(
        world_calendar, "encounter_multipliers", lambda r, s: {"mon_arame_vivo": 2.0}
    )
    loc = gamedata.get_location(LAMA)
    rows = dict(
        (e["id"], w)
        for e, w in wu.encounter_distribution(
            loc, 3, 100, bestiary_knowledge={}, projection={}, season="verao",
            world=_world(), world_sim={},
        )
    )  # fmt: skip
    base = dict(
        (e["id"], w)
        for e, w in wu.encounter_distribution(
            loc, 3, 100, bestiary_knowledge={}, projection={}, season=None,
            world=_world(), world_sim={},
        )
    )  # fmt: skip
    assert rows["mon_arame_vivo"] == pytest.approx(base["mon_arame_vivo"] * 0.7)


def test_fator_territorio():
    e = fauna.entry("mon_porca_da_queda")  # territorio: Anel de Lama
    assert fauna.eco_multiplier(e, _ctx(loc=LAMA))[0] == 1.0
    f, why = fauna.eco_multiplier(e, _ctx(loc=FERRO))
    assert f == pytest.approx(fauna.const("TERRITORIO_FORA")) and "territorio" in why


def test_presa_liberada_quando_predador_cacado():
    rato = fauna.entry("enemy_rato_peste_anel_lama")
    assert "mon_porca_da_queda" in rato["predadores"]
    hunted = {"mon_porca_da_queda": {"defeated": 6, "last_update_turn": 100}}
    f, why = fauna.eco_multiplier(rato, _ctx(bk=hunted))
    assert "presa_liberada" in why and f == pytest.approx(fauna.const("PRESA_LIBERADA") * 1.0)


def test_predador_faminto():
    porca = fauna.entry("mon_porca_da_queda")
    preys = porca["ecologia"]["presas"]
    bk = {q: {"defeated": 6, "last_update_turn": 100} for q in preys}
    f, why = fauna.eco_multiplier(porca, _ctx(bk=bk))
    assert "predador_faminto" in why and f == pytest.approx(fauna.const("PREDADOR_FAMINTO"))


def test_reage_pressao_clima_carcaca():
    arame = fauna.entry("mon_arame_vivo")  # clima:chuva mais, pressao:praga mais
    f, _ = fauna.eco_multiplier(arame, _ctx(weather_state="chuva"))
    assert f == pytest.approx(fauna.const("REAGE_MAIS"))
    f, _ = fauna.eco_multiplier(arame, _ctx(pressure_bands={"praga": "crise"}))
    assert f == pytest.approx(fauna.const("REAGE_MAIS"))
    f, _ = fauna.eco_multiplier(arame, _ctx(pressure_bands={"praga": "normal"}))
    assert f == 1.0
    rato = fauna.entry("enemy_rato_peste_anel_lama")  # carcaca_recente mais
    f, why = fauna.eco_multiplier(rato, _ctx(carcacas_aqui=["mon_porca_da_queda"]))
    assert any(w.startswith("reage:carcaca_recente") for w in why)
    bagre = fauna.entry("enemy_polvo_esgoto")  # clima:limpo menos
    f, _ = fauna.eco_multiplier(bagre, _ctx(weather_state="limpo"))
    assert f == pytest.approx(fauna.const("REAGE_MENOS"))


def test_reage_some_zera():
    e = {"ecologia": {"reage": [{"quando": "clima:chuva", "efeito": "some"}]}, "predadores": []}
    assert fauna.eco_multiplier(e, _ctx(weather_state="chuva"))[0] == 0.0


def test_foge_de_presenca():
    rato = fauna.entry("enemy_rato_peste_anel_lama")  # foge_de porca
    f, why = fauna.eco_multiplier(rato, _ctx(presencas_aqui=["mon_porca_da_queda"]))
    assert "foge_de" in why and f == pytest.approx(fauna.const("FOGE_DE"))


def test_sem_entrada_fator_1(on):
    """Criatura sem fauna (ex.: legado de outra regiao) pesa como antes."""
    cid = "enemy_assassino_cinzeu"
    assert fauna.entry(cid) is None
    loc = gamedata.get_location(LAMA)
    on_rows = dict((e["id"], w) for e, w in wu.encounter_distribution(
        loc, 3, 100, bestiary_knowledge={}, projection={}, world=_world(), world_sim={}))  # fmt: skip
    assert on_rows[cid] == pytest.approx(1.0)


def test_taxa_de_gatilho_inalterada(monkeypatch):
    """R9: o sorteio so escolhe QUEM; nas mesmas seeds o numero de gatilhos e igual."""

    def run(mode):
        monkeypatch.setenv("RPG_FAUNA", mode)
        monkeypatch.setenv("RPG_FAUNA_SINAIS", mode)
        hits = 0
        for t in range(60):
            world = {
                "current_location_id": [LAMA, FERRO, DOURADO][t % 3],
                "world_clock": {"day": 1 + t // 4, "period": wu.PERIODS[t % 5]},
                "danger_overrides": {LAMA: 4, FERRO: 4, DOURADO: 4},
                "last_encounter_turn": -99 if t % 2 else t - 1,
            }
            random.seed(t)
            enc = wu.check_encounter(
                world, [], {}, t, bestiary_knowledge={}, projection={}, player_level=5,
                world_sim={} if mode != "off" else None,
            )  # fmt: skip
            hits += bool(enc)
        return hits

    assert run("off") == run("on") > 0


def test_shadow_nao_muda_escolha_e_loga(monkeypatch):
    import observability.telemetry as tel

    events = []
    monkeypatch.setattr(tel, "log_event", lambda *a, **k: events.append((a, k)))
    loc = gamedata.get_location(LAMA)
    picks = {}
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_FAUNA", mode)
        out = []
        for t in range(20):
            out.append(
                wu.pick_encounter_enemy(
                    loc, 3, t, bestiary_knowledge={}, projection={},
                    rng=random.Random(t), world=_world(period="Manhã"), world_sim={},
                )["id"]
            )  # fmt: skip
        picks[mode] = out
    assert picks["off"] == picks["shadow"]
    assert any(a[:2] == ("fauna", "shadow_pick") for a, _k in events)


def test_off_byte_identico(monkeypatch):
    """Com `RPG_FAUNA=off`, passar `world`/`world_sim` nao muda o sorteio legado."""
    monkeypatch.setenv("RPG_FAUNA", "off")
    loc = gamedata.get_location(LAMA)
    for t in range(15):
        a = wu.pick_encounter_enemy(
            loc, 3, t, bestiary_knowledge={}, projection={}, rng=random.Random(t)
        )
        b = wu.pick_encounter_enemy(
            loc, 3, t, bestiary_knowledge={}, projection={}, rng=random.Random(t),
            world=_world(), world_sim={"fauna": {"presencas": []}},
        )  # fmt: skip
        assert a["id"] == b["id"]


def test_carcaca_registrada_e_expira(on):
    sim = fauna.record_kill({}, "mon_porca_da_queda", LAMA, 3)
    assert sim["fauna"]["carcacas"] == [
        {"loc": LAMA, "day": 3, "creature_id": "mon_porca_da_queda"}
    ]
    ctx = fauna.eco_ctx(_world(), sim, location_id=LAMA, region_id="nova_arcadia",
                        bestiary_knowledge={}, turn=1, season=None)  # fmt: skip
    assert ctx.carcacas_aqui == ["mon_porca_da_queda"]
    later = {"current_location_id": LAMA, "world_clock": {"day": 3 + 3}}
    ctx = fauna.eco_ctx(later, sim, location_id=LAMA, region_id="nova_arcadia",
                        bestiary_knowledge={}, turn=1, season=None)  # fmt: skip
    assert ctx.carcacas_aqui == []
    for _d in range(30):
        sim = fauna.record_kill(sim, "mon_porca_da_queda", LAMA, 3)
    assert len(sim["fauna"]["carcacas"]) == fauna.const("MAX_CARCACAS")
    assert fauna.record_kill({}, "enemy_assassino_cinzeu", LAMA, 3) == {}
