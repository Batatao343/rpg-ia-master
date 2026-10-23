"""SPEC-302 Etapa 5: efeitos de estado de local e relacoes/progresso de faccoes."""

from __future__ import annotations

import copy

import pytest

import gamedata
import world_utils as wu
from services import economy
from services import faction_relations as fr
from services import world_director as wd
from services import world_engine as we
from services import world_pressures as wp
from services.event_processor import apply_event
from tests.spec302_helpers import fresh_sim, make_state, set_pressure, tick


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


def _state_with(loc, state_name, sev=2):
    return {
        "world": {"current_location_id": loc, "world_clock": {"day": 5, "period": "Manhã"}},
        "world_projection": {"location_states": {loc: {"state": state_name, "severity": sev}}},
    }


ITEM = "espada_aco_temperado"


def test_price_mult_from_location_state(monkeypatch):
    base_state = {"world": {"current_location_id": "skallgard"}, "world_projection": {}}
    base = economy.price(ITEM, mode="buy", state=base_state)
    st = _state_with("skallgard", "escassez", 2)
    assert abs(economy.price(ITEM, mode="buy", state=st) - base * 1.5) <= 5
    assert economy.price(ITEM, mode="sell", state=st) == economy.price(
        ITEM, mode="sell", state=base_state
    )
    for m in ("off", "shadow"):
        monkeypatch.setenv("RPG_WORLD_ENGINE", m)
        assert economy.price(ITEM, mode="buy", state=st) == base


def test_restock_respects_state():
    def world():
        return {
            "world_clock": {"day": 20},
            "merchant_stocks": {"ferreiro_skallgard": {"x": 1}},
            "merchant_restock_day": {"ferreiro_skallgard": 1},
        }

    plain = economy.restock(world(), projection={})
    assert plain["merchant_stocks"]["ferreiro_skallgard"] != {"x": 1}
    ruin = {"location_states": {"skallgard": {"state": "ruina", "severity": 1}}}
    assert economy.restock(world(), projection=ruin)["merchant_stocks"]["ferreiro_skallgard"] == {
        "x": 1
    }
    slow = {
        "location_states": {"skallgard": {"state": "escassez", "severity": 1}}
    }  # 0.5 -> intervalo 6
    w = world()
    w["world_clock"]["day"] = 5  # 4 dias desde o ultimo restock: normal (3) repoe, escassez (6) nao
    assert economy.restock(w, projection=slow)["merchant_stocks"]["ferreiro_skallgard"] == {"x": 1}


def test_effective_danger_adds_delta_clamped(monkeypatch):
    base = int(gamedata.get_location("skallgard").get("danger", 1))
    world = {"current_location_id": "skallgard", "location_danger_delta": {"skallgard": 1}}
    assert wu.effective_danger(world) == min(4, base + 1) or base >= 4
    assert wu.effective_danger({**world, "location_danger_delta": {"skallgard": 9}}) <= max(4, base)
    monkeypatch.setenv("RPG_WORLD_ENGINE", "shadow")
    assert wu.effective_danger(world) == base
    safe = {"current_location_id": "nova_arcadia", "location_danger_delta": {}}
    assert wu.effective_danger(safe) == int(gamedata.get_location("nova_arcadia")["danger"])


def test_engine_writes_danger_delta_cache_without_safe_havens():
    from services import location_states as ls

    assert ls.danger_delta({"state": "cerco"}, "nova_arcadia") == 0  # tag `seguro`
    assert ls.danger_delta({"state": "cerco"}, "skallgard") == 1


def test_relations_seeded_from_enemy_edges():
    rel = fr.seed_relations(gamedata.seed_factions())
    assert rel["filhos_chama_azul|legiao_ferro"] == -60
    assert rel["druidas_ciclo_cinzento|druidas_renegados"] == -60
    assert len(rel) == 19 * 18 // 2


def _pair_sim(value):
    st = make_state("rel")
    tick(st, 1, 2)
    st["world_sim"]["faction_relations"]["filhos_chama_azul|legiao_ferro"] = value
    return st


def test_war_crossing_goes_through_director():
    st = _pair_sim(-75)
    base = st["world_sim"]["pressures"]["nova_arcadia"]["guerra"]
    res = tick(st, 2, 3)
    ev = [e for e in res.pending_events if e["type"] == "faction_relation_changed"]
    assert ev and ev[0]["payload"]["relation"] == "enemy_of"
    assert res.world_sim["pressures"]["nova_arcadia"]["guerra"] >= base + fr.WAR_BOOST - 10
    # nenhum cerco abre no mesmo dia: aviso primeiro (R13)
    assert not [e for e in res.pending_events if e["type"] == "location_state_changed"]


def test_alliance_is_signal_not_crisis():
    st = _pair_sim(65)
    res = tick(st, 2, 3)
    ev = [e for e in res.pending_events if e["type"] == "faction_relation_changed"]
    assert ev and ev[0]["payload"]["relation"] == "allied_with"
    assert any(d["kind"] == "relacao" for d in res.digest)
    assert not wd.active_crises(res.world_sim)


def test_neutral_disables_dynamic_edge():
    ev = {
        "type": "faction_relation_changed",
        "event_id": "e1",
        "target_id": "legiao_ferro",
        "turn": 1,
        "payload": {"other_faction_id": "mao_sombria", "relation": "enemy_of"},
    }
    proj = apply_event(ev, {})
    assert proj["dynamic_edges"]
    back = apply_event(
        {
            **ev,
            "event_id": "e2",
            "payload": {"other_faction_id": "mao_sombria", "relation": "neutral"},
        },
        proj,
    )
    assert back["dynamic_edges"] == []


def test_faction_progress_daily_and_ascension_gated():
    sim = fresh_sim()
    facs = gamedata.seed_factions()
    legiao = next(f for f in facs if f["id"] == "legiao_ferro")
    legiao["progress"] = 100
    # teto de crises ativo: sem vaga a ascensao espera e NAO perde progresso
    sim["crises"] = [
        {
            "crisis_id": str(i),
            "kind": "fome",
            "region_id": r,
            "start_day": 1,
            "end_day": None,
            "severity": 1,
            "warned_day": 0,
            "escalation_day": 9,
            "location_id": "",
            "loc_state": "",
            "faction_id": "",
        }
        for i, r in enumerate(("brekmar", "pradaria_ruinas"))
    ]
    wd.announce(sim, 1, "nova_arcadia", "ascensao", game_id="g", faction_id="legiao_ferro")
    # (announce respeita o teto; registra manualmente o aviso antigo)
    sim["crises"].append(
        {
            "crisis_id": "a",
            "kind": "ascensao",
            "region_id": "nova_arcadia",
            "start_day": None,
            "end_day": None,
            "severity": 0,
            "warned_day": 1,
            "escalation_day": None,
            "location_id": "",
            "loc_state": "",
            "faction_id": "legiao_ferro",
        }
    )
    cfg = wp.get_config()
    world, out, _ev, _dg = we._ascension_step(
        sim, 10, "g", {}, facs, {}, cfg, we.day_rng("g", 10, "d")
    )
    f = next(x for x in out if x["id"] == "legiao_ferro")
    assert not f.get("completed") and f["progress"] == 100
    assert "controlled" not in world
    # libera vaga: agora ascende
    sim["crises"] = [c for c in sim["crises"] if c["kind"] == "ascensao"]
    sim.pop("last_crisis_start_day", None)
    world, out, _ev, dg = we._ascension_step(
        sim, 10, "g", {}, facs, {}, cfg, we.day_rng("g", 10, "d")
    )
    f = next(x for x in out if x["id"] == "legiao_ferro")
    assert (
        f.get("completed") and (world.get("controlled") or {}).get("na_anel_lama") == "legiao_ferro"
    )
    assert any(d["kind"] == "ascensao" for d in dg)


def test_ascension_warned_at_80():
    sim = fresh_sim()
    facs = gamedata.seed_factions()
    next(f for f in facs if f["id"] == "legiao_ferro")["progress"] = 85
    _w, _f, ev, dg = we._ascension_step(
        sim, 10, "g", {}, facs, {}, wp.get_config(), we.day_rng("g", 10, "d")
    )
    assert [e["type"] for e in ev] == ["world_crisis_warning"]
    assert ev[0]["payload"]["kind"] == "ascensao"
    assert dg[0]["kind"] == "aviso"
    snapshot = copy.deepcopy(sim["crises"])
    we._ascension_step(sim, 10, "g", {}, facs, {}, wp.get_config(), we.day_rng("g", 10, "d"))
    assert sim["crises"] == snapshot  # nao reanuncia


def test_faction_region_id_mapping():
    regions = set(wp.region_ids())
    facs = gamedata.seed_factions()
    assert len(facs) == 19
    for f in facs:
        assert we.faction_region_id(f) in regions, f["id"]


def test_faction_progress_runs_inside_tick_not_legacy_path():
    st = make_state("prog")
    st["factions"] = gamedata.seed_factions()
    res = tick(st, 1, 9)
    assert any(f["progress"] > 0 for f in res.factions)
    assert all(f["progress"] < 100 for f in res.factions)  # FACTION_DAY_FACTOR: sem saturar em dias
    set_pressure(fresh_sim(), "nova_arcadia", "guerra", 1)
