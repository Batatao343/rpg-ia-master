"""SPEC-372 Etapa 5 — motor: portao, puxao, presenca nos locais, track, taxa."""

from __future__ import annotations

import pytest

from scripts.fauna import eval as ev360
from services import fauna, fauna_tramas
from services import plot_threads as pt

CORPOS = "tr_na_corpos_marcados"
DORM = {t.id: "dormente" for t in pt.threads_for_region("nova_arcadia")}
TOCADA = {**DORM, CORPOS: "tocada"}


@pytest.fixture
def flags(monkeypatch):
    for k, v in {
        "RPG_FAUNA": "on",
        "RPG_FAUNA_SINAIS": "on",
        "RPG_PLOT_THREADS": "on",
        "RPG_WORLD_ENGINE": "on",
        "RPG_FAUNA_TRAMAS": "on",
    }.items():
        monkeypatch.setenv(k, v)
    pt.clear_cache()
    yield monkeypatch
    pt.clear_cache()


def _dist(loc: str, stages, period="Tarde") -> dict[str, float]:
    import gamedata
    import world_utils as wu

    rows = wu.encounter_distribution(
        gamedata.get_location(loc) or {},
        ev360.PLAYER_LEVEL,
        100,
        bestiary_knowledge={},
        projection={},
        world=ev360._neutral_world(loc, period),
        world_sim={},
        trama_stages=stages,
    )
    tot = sum(w for _e, w in rows) or 1.0
    return {str(e["id"]): w / tot for e, w in rows}


def _link(monkeypatch, cid: str, desde="tocada"):
    real = fauna.load()
    ent = {**real[cid], "tramas": [{"id": CORPOS, "desde": desde}]}
    monkeypatch.setattr(fauna, "load", lambda: {**real, cid: ent})


def _pick(loc_ids) -> tuple[str, str]:
    """(creature, location) com fatia > 0 num local da trama, sem link (flag off)."""
    for loc in loc_ids:
        d = _dist(loc, None)
        for cid, _share in sorted(d.items(), key=lambda kv: -kv[1]):
            if fauna.entry(cid):
                return cid, loc
    raise AssertionError("sem criatura de fauna")


def test_portao_zera_antes_do_estagio(flags):
    locs = list(pt.thread(CORPOS).locations)
    cid, loc = _pick(locs)
    _link(flags, cid)
    assert _dist(loc, DORM).get(cid, 0.0) == 0.0
    assert _dist(loc, TOCADA).get(cid, 0.0) > 0.0


def test_portao_vale_no_fallback_legado(flags):
    import gamedata
    import world_utils as wu

    locs = list(pt.thread(CORPOS).locations)
    cid, loc = _pick(locs)
    _link(flags, cid)
    # todos os fatores ecologicos 0 => sum(eco_weights)==0 => pesos legados; portao continua
    flags.setattr(
        fauna,
        "eco_multiplier",
        lambda e, c: (
            (0.0, [])
            if not fauna_tramas.gate_closed(e, c.trama_stages)
            else (0.0, ["trama_dormente"])
        ),
    )
    rows = wu.encounter_distribution(
        gamedata.get_location(loc) or {},
        ev360.PLAYER_LEVEL,
        100,
        bestiary_knowledge={},
        projection={},
        world=ev360._neutral_world(loc, "Tarde"),
        world_sim={},
        trama_stages=DORM,
    )
    assert rows and all(e["id"] != cid for e, _w in rows)


def test_puxao_nos_locais(flags):
    locs = list(pt.thread(CORPOS).locations)
    cid, loc = _pick(locs)
    _link(flags, cid)
    on = _dist(loc, TOCADA)[cid]
    flags.setenv("RPG_FAUNA_TRAMAS", "off")
    off = _dist(loc, TOCADA)[cid]
    assert on > off * 1.4


def test_fora_dos_locais_neutro(flags):
    cid, loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    e = fauna.entry(cid)
    ctx = fauna.EcoCtx(
        location_id="na_fora",
        region_id="nova_arcadia",
        period=None,
        season=None,
        trama_stages=TOCADA,
    )
    f, why = fauna_tramas.factor(e, "na_fora", TOCADA)
    assert f == 1.0 and why == f"trama:{CORPOS}"
    assert ctx.trama_stages is TOCADA
    assert fauna_tramas.factor(e, "", TOCADA)[0] == 1.0  # contexto regional do day_hook


def test_flag_off_ou_sem_requisito_ignora(flags):
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    e = fauna.entry(cid)
    assert fauna_tramas.factor(e, "x", DORM)[0] == 0.0
    flags.setenv("RPG_PLOT_THREADS", "off")
    assert fauna.tramas_mode() == "off"
    assert fauna_tramas.factor(e, "x", DORM) == (1.0, None)
    flags.setenv("RPG_PLOT_THREADS", "on")
    flags.setenv("RPG_FAUNA", "off")
    assert fauna.tramas_mode() == "off"


def test_birth_restringe_aos_locais_da_trama(flags):
    cid, loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    e = fauna.entry(cid)
    thr_locs = set(pt.thread(CORPOS).locations)
    out, tid = fauna_tramas.birth(e, TOCADA, [*thr_locs, "na_fora"])
    assert set(out) <= thr_locs and "na_fora" not in out and tid == CORPOS
    assert fauna_tramas.birth(e, DORM, ["na_fora"]) == ([], "")
    assert fauna_tramas.birth({"id": "x"}, TOCADA, ["a"]) is None


def test_open_pool_respeita_portao(flags):  # ramo legado/track: pool sem a criatura
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    pool = [{"id": cid}, {"id": "outra_sem_fauna"}]
    assert [e["id"] for e in fauna_tramas.open_pool(pool, DORM)] == ["outra_sem_fauna"]
    assert len(fauna_tramas.open_pool(pool, TOCADA)) == 2


def test_presenca_sem_trama_id_com_flag_off(flags):
    flags.setenv("RPG_FAUNA_TRAMAS", "off")
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    assert fauna_tramas.birth(fauna.entry(cid), TOCADA, ["a"]) is None
    row = fauna.normalize_fauna_sim({"presencas": [{"pid": "p", "creature_id": cid}]})
    assert "trama_id" not in row["presencas"][0]
    row = fauna.normalize_fauna_sim(
        {"presencas": [{"pid": "p", "creature_id": cid, "trama_id": CORPOS}]}
    )
    assert row["presencas"][0]["trama_id"] == CORPOS


def test_taxa_de_gatilho_inalterada(flags):
    """O portao so muda QUEM: check_encounter dispara igual com a flag on e off."""
    import gamedata
    import world_utils as wu

    cid, loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)

    def run(flag: str, stages):
        flags.setenv("RPG_FAUNA_TRAMAS", flag)
        n = 0
        for turn in range(1, 60):
            world = ev360._neutral_world(loc, "Tarde")
            world["turn_count"] = turn
            enc = wu.check_encounter(
                world,
                [],
                {},
                turn * 10,
                bestiary_knowledge={},
                projection={},
                player_level=ev360.PLAYER_LEVEL,
                world_sim={},
                trama_stages=stages,
            )
            n += 1 if enc else 0
        return n

    assert gamedata.get_location(loc)
    assert run("on", DORM) == run("off", DORM) == run("on", TOCADA)


def test_day_hook_presenca_nasce_nos_locais_com_trama_id(flags):
    """R10: toda presenca `dia` de ligada atingida nasce nos locais da trama, com `trama_id`."""
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    real = fauna.load()
    # so a ligada compete: as demais criaturas da regiao saem do pool
    only = {k: v for k, v in real.items() if k == cid or v.get("regiao") != "nova_arcadia"}
    only[cid] = {**real[cid], "tramas": [{"id": CORPOS, "desde": "tocada"}]}
    flags.setattr(fauna, "load", lambda: only)
    thr_locs = set(pt.thread(CORPOS).locations)
    got = []
    for seed in range(12):
        st = ev360._new_state(seed)
        st["npcs"] = {"npc_tr_pio_ferrugem": {"id": "npc_tr_pio_ferrugem", "known_by_player": True}}
        for day in range(1, 15):
            st["world"]["world_clock"] = {"day": day, "period": "Tarde"}
            ev360._run_day_hooks(st, day)
        got += [p for p in st["world_sim"]["fauna"]["presencas"] if p["creature_id"] == cid]
    assert got, "nenhuma presenca nasceu"
    assert all(p.get("trama_id") == CORPOS and set(p["locais"]) <= thr_locs for p in got)


def test_day_hook_portao_sem_estagio(flags):
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    real = fauna.load()
    only = {k: v for k, v in real.items() if k == cid or v.get("regiao") != "nova_arcadia"}
    only[cid] = {**real[cid], "tramas": [{"id": CORPOS, "desde": "tocada"}]}
    flags.setattr(fauna, "load", lambda: only)
    for seed in range(12):
        st = ev360._new_state(seed)
        for day in range(1, 15):
            st["world"]["world_clock"] = {"day": day, "period": "Tarde"}
            ev360._run_day_hooks(st, day)
        pres = st["world_sim"]["fauna"]["presencas"]
        assert not [p for p in pres if p["creature_id"] == cid]


def test_invariante_trama_id_exige_ligacao(flags):
    from playtest import invariants as inv

    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    e = fauna.entry(cid)
    locs = list(pt.thread(CORPOS).locations)
    ok = {"creature_id": cid, "trama_id": CORPOS, "locais": locs[:1]}
    assert inv._trama_presence_errors(ok, e, 1) == []
    assert inv._trama_presence_errors({**ok, "locais": ["na_fora"]}, e, 1)
    assert inv._trama_presence_errors({**ok, "trama_id": "tr_na_nada"}, e, 1)
    assert inv._trama_presence_errors({"creature_id": cid}, e, 1) == []
