"""SPEC-372 Etapa 5 — motor: portao, puxao, presenca nos locais, track, taxa."""

from __future__ import annotations

import json

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


def test_track_respeita_portao(flags):
    """P1-1: `resolve_track` (rastro em jogo) nao sorteia criatura atras do portao."""
    import gamedata
    import world_utils as wu

    cid, loc_id = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    loc = gamedata.get_location(loc_id)
    pool = [e["id"] for e in wu._encounter_pool(loc, 3, None)[0]]
    assert cid in pool
    seen_dorm, seen_open = set(), set()
    for turn in range(len(pool) * 2):
        _bk, note, _t = wu.resolve_track({}, loc, 3, turn, trama_stages=DORM)
        entry = wu.pick_encounter_enemy(loc, 3, turn, trama_stages=DORM)
        seen_dorm.add(entry["id"])
        seen_open.add(wu.pick_encounter_enemy(loc, 3, turn, trama_stages=TOCADA)["id"])
        assert _bk.get(cid) is None
    assert cid not in seen_dorm and cid in seen_open


def test_presenca_atras_do_portao_nao_decide_encontro(flags):
    import world_utils as wu

    cid, loc_id = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    sim = {
        "fauna": {
            "presencas": [
                {
                    "pid": "p",
                    "creature_id": cid,
                    "region_id": "nova_arcadia",
                    "locais": [loc_id],
                    "born_day": 1,
                    "expires_day": 9,
                    "sinais_mostrados": [],
                    "origem": "rastro",
                    "status": "ativa",
                }
            ]
        }
    }
    world = {"world_clock": {"day": 2}}
    assert wu._fauna_presence(world, sim, loc_id) is not None
    assert wu._fauna_presence(world, sim, loc_id, DORM) is None
    assert wu._fauna_presence(world, sim, loc_id, TOCADA) is not None


def test_encounter_budget_e_rumor_respeitam_portao(flags):
    import encounter_budget as eb
    import gamedata

    cid, loc_id = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    loc = gamedata.get_location(loc_id)
    got = set()

    def make(entry, i):
        got.add(entry["id"])
        return {"id": entry["id"], "name": "x", "type": "minion"}

    for turn in range(40):
        eb.fill_encounter([], 40, loc, 3, turn=turn, make_instance=make, trama_stages=DORM)
    assert got and cid not in got


def test_puxao_telemetria(flags):
    seen = []
    flags.setattr(fauna, "_log", lambda name, **kw: seen.append((name, kw)))
    cid, loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    fauna_tramas.log_pull({"id": cid}, TOCADA, loc)
    fauna_tramas.log_pull({"id": cid}, TOCADA, "na_fora")
    assert [n for n, _ in seen] == ["trama_puxao"] and seen[0][1]["thread"] == CORPOS


def test_save_load_preserva_trama_id(flags, tmp_path):
    """P2-5: round-trip da presenca com `trama_id`; save antigo (sem a chave) segue igual."""
    cid, _loc = _pick(list(pt.thread(CORPOS).locations))
    raw = {
        "presencas": [
            {"pid": "a", "creature_id": cid, "trama_id": CORPOS},
            {"pid": "b", "creature_id": cid},
        ]
    }
    once = fauna.normalize_fauna_sim(raw)
    twice = fauna.normalize_fauna_sim(json.loads(json.dumps(once)))
    assert once == twice
    assert twice["presencas"][0]["trama_id"] == CORPOS and "trama_id" not in twice["presencas"][1]


def test_faccao_dominante_respeita_portao(flags):
    """P2-8: facção sem combatente próprio (`poder_kahen`) cai no sorteio de região, com portão."""
    import gamedata
    import world_utils as wu

    cid, loc_id = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    assert wu._bestiary_by_faction("poder_kahen") is None
    flags.setattr(wu, "_hostile_ruler", lambda *a, **k: {"id": "poder_kahen", "name": "Kahen"})
    seen = set()
    for turn in range(100, 160):
        world = ev360._neutral_world(loc_id, "Tarde")
        enc = wu.check_encounter(
            world, [], {}, turn * 10, bestiary_knowledge={}, projection={}, trama_stages=DORM
        )
        assert enc and enc["reason"] == "controlled"
        seen.add(enc["enemy_id"])
    assert gamedata.get_location(loc_id) and seen and cid not in seen


def test_rumor_adoption_encounter_hint_respeita_portao(flags):
    """P2-9: o encontro de rumor adotado (tipo != criatura_avistada) respeita o portão."""
    import gamedata
    from services import rumor_adoption as ra

    cid, loc_id = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    flags.setattr(ra, "_unused", None, raising=False)
    # estado com a trama dormente: nenhum sinal; a trama so abre com rumor percebido da semente
    state = {"game_id": "g", "bestiary_knowledge": {}, "world_projection": {}}
    world = {
        "current_location_id": loc_id,
        "world_clock": {"day": 3, "period": "Tarde"},
    }
    assert gamedata.get_location(loc_id)
    seen = set()
    for i in range(60):
        inst = {"rumor_id": f"r{i}", "claim": {"kind": "emboscada"}}
        hint = ra.encounter_hint(state, inst, world, ev360.PLAYER_LEVEL, i)
        if hint:
            seen.add(hint["enemy_id"])
    assert seen and cid not in seen
    # com a trama atingida, a criatura volta a poder sair
    state["world_sim"] = {
        "rumors": [{"rumor_id": "x", "seed_id": pt.thread(CORPOS).rumor_ids[0], "perceived_day": 2}]
    }
    seen = set()
    for i in range(200):
        inst = {"rumor_id": f"s{i}", "claim": {"kind": "emboscada"}}
        hint = ra.encounter_hint(state, inst, world, ev360.PLAYER_LEVEL, i)
        if hint:
            seen.add(hint["enemy_id"])
    assert cid in seen


def test_trama_regride_dispersa_presenca_e_cala_sinal(flags):
    """P2-10: presenca ligada cujo portao fecha deixa o teto da regiao e nao mostra sinal."""
    cid, loc = _pick(list(pt.thread(CORPOS).locations))
    _link(flags, cid)
    flags.setattr(fauna, "region_cap", lambda region: 1)  # regiao de 1 vaga
    pres = {
        "pid": "p1",
        "creature_id": cid,
        "region_id": "nova_arcadia",
        "locais": [loc],
        "born_day": 1,
        "expires_day": 9,
        "sinais_mostrados": [],
        "origem": "dia",
        "status": "ativa",
        "trama_id": CORPOS,
    }
    # tocada: ainda ativa e com sinal
    st_on = {"npcs": {"npc_tr_pio_ferrugem": {"known_by_player": True}}}
    st_on["world"] = {"current_location_id": loc, "world_clock": {"day": 2}}
    st_on["world_sim"] = {"fauna": {"v": 1, "presencas": [dict(pres)], "carcacas": []}}
    block, _upd = fauna.scene_block(st_on)
    assert block
    # a trama regrediu (sem NPC conhecido): sem sinal, e o hook a dispersa
    st_off = {"npcs": {}, "world": st_on["world"]}
    st_off["world_sim"] = {"fauna": {"v": 1, "presencas": [dict(pres)], "carcacas": []}}
    assert fauna.scene_block(st_off) == ("", {})
    sim = st_off["world_sim"]
    fa = fauna._fauna_of(sim)
    fauna_tramas.disperse_closed(fa, st_off, 2)
    assert fa["presencas"][0]["status"] == "dispersa"
    active = [p for p in fa["presencas"] if fauna._active(p, 2)]
    assert len(active) == 0 < fauna.region_cap("nova_arcadia")
