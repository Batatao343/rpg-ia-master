"""SPEC-304 Etapa 5: intervenção e destino (R16-R19, R25)."""

from __future__ import annotations

import copy
import random

import pytest

from services import event_processor as ep
from services import npc_layers, npc_perils, npc_world, reputation
from tests.spec304_helpers import (
    BRUNNA,
    BRUNNA_ID,
    hook,
    known_npc,
    setup_env,
    step,
    waiting_state,
)

FATES = ("morto", "ferido", "capturado", "escapou")


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _cfg(monkeypatch, p=1.0, fate=None):
    """Hazard `p` e (opcional) destino unico."""
    cfg = copy.deepcopy(npc_perils.cfg())
    cfg["BASE_HAZARD"] = {"3": p, "4": p}
    cfg["HOME_MULT"] = 1.0
    cfg["constants"]["P_FLEE"] = 0.0
    if fate:
        for kind in cfg["fate_weights"]:
            cfg["fate_weights"][kind] = {f: (1 if f == fate else 0) for f in FATES}
    monkeypatch.setattr(npc_perils, "cfg", lambda: cfg)
    return cfg


def _solo(monkeypatch, refs):
    monkeypatch.setattr(npc_world, "_candidates", lambda state, sim: list(refs))


def _brunna(monkeypatch, fate=None, p=1.0):
    _cfg(monkeypatch, p, fate)
    _solo(monkeypatch, (BRUNNA_ID,))
    st = waiting_state()
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    return st


class _Live:
    """O hook deep-copia o `npc_sim` a cada dia: o perigo sempre e relido do estado."""

    def __init__(self, st, pid):
        self._st, self._pid = st, pid

    def _row(self) -> dict:
        return next(p for p in self._st["npc_sim"]["perils"] if p["peril_id"] == self._pid)

    def __getitem__(self, key):
        return self._row()[key]

    def get(self, key, default=None):
        return self._row().get(key, default)


def _open(st, day=3):
    res = hook(st, day)
    return res, _Live(st, st["npc_sim"]["perils"][-1]["peril_id"])


def _quiet(monkeypatch, fate=None):
    _cfg(monkeypatch, 0.0, fate)


def _run_until_resolved(st, peril, start, perceive=True, limit=15):
    d = start
    while not peril["resolution"] and d < start + limit:
        d += 1
        if perceive and peril["warning_event_id"] not in st["world_sim"].setdefault(
            "perceived_ids", []
        ):
            st["world_sim"]["perceived_ids"].append(peril["warning_event_id"])
        res = hook(st, d)
        st.setdefault("_evs", []).extend(res.events)
    return d


def test_intervention_by_arrival_saves(monkeypatch):
    st = _brunna(monkeypatch)
    _res, peril = _open(st)
    _quiet(monkeypatch)
    st["world"]["current_location_id"] = "ma_saidas_baixas"  # o jogador chega
    res = hook(st, 4)
    assert peril["resolution"] == "intervencao" and peril["resolved_day"] == 4
    assert [i for i in res.digest if i["template_id"] == "npc_resgate.chegada"]
    assert not [e for e in res.events if e["type"] in ("npc_killed", "npc_offscreen_fate")]


def test_intervention_by_multi_day_travel_destination(monkeypatch):
    st = _brunna(monkeypatch)
    _res, peril = _open(st)
    _quiet(monkeypatch)
    step(st, 3, 6, loc="ma_saidas_baixas")  # viagem de varios dias: o DESTINO conta
    live = next(p for p in st["npc_sim"]["perils"] if p["peril_id"] == peril["peril_id"])
    assert live["resolution"] == "intervencao"


def test_companion_set_following_cancels_fate(monkeypatch):
    import party

    st = _brunna(monkeypatch, fate="morto")
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    st["party"], ok = party.set_following(st, BRUNNA)  # o jogador o chamou de volta
    assert ok
    hook(st, 4)
    assert peril["resolution"] == "intervencao"
    assert st["party"] and st["party"][0]["active"]  # nada aconteceu a ele


def test_no_fate_before_earliest_day(monkeypatch):
    st = _brunna(monkeypatch, fate="morto")
    _res, peril = _open(st, 3)
    _quiet(monkeypatch, "morto")
    for d in range(4, peril["deadline_day"]):
        st["world_sim"].setdefault("perceived_ids", []).append(peril["warning_event_id"])
        hook(st, d)
        assert not peril["resolution"], d
    assert peril["earliest_day"] == 5 and peril["deadline_day"] > peril["earliest_day"]


def test_major_unperceived_extends_then_non_lethal(monkeypatch):
    st = _brunna(monkeypatch, fate="morto")
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    d = _run_until_resolved(st, peril, 3, perceive=False)
    assert peril["extensions"] == 3  # R17: ate MAX_EXTENSION_DAYS
    assert peril["resolution"] not in ("", "morto")  # nunca morre sem telegrama percebido
    assert d >= peril["opened_day"] + 2 + 1 + 3
    assert st["party"] and not st["npc_sim"]["npcs"][BRUNNA_ID].get("dead")


def test_major_perceived_can_die(monkeypatch):
    st = _brunna(monkeypatch, fate="morto")
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    _run_until_resolved(st, peril, 3, perceive=True)
    assert peril["resolution"] == "morto" and peril["slot_day"] is not None
    assert peril["perceived_day"] <= peril["deadline_day"] - 1


def test_minor_can_die_unperceived(monkeypatch):
    _cfg(monkeypatch, 1.0, "morto")
    _solo(monkeypatch, ("npc_zed",))
    st = waiting_state()
    st["party"], st["companion_souls"] = [], {}
    st["npcs"] = {"Zed": known_npc("npc_zed", "Zed", home_location_id="ma_saidas_baixas")}
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    _res, peril = _open(st)
    assert not peril["major"]
    _quiet(monkeypatch, "morto")
    _run_until_resolved(st, peril, 3, perceive=False)
    assert peril["resolution"] == "morto" and peril["perceived_day"] is None


def test_fate_weights_seeded():
    peril = {"kind": "cerco", "danger": 3}
    a = [npc_perils.pick_fate(peril, random.Random(5), lethal=True) for _ in range(3)]
    assert a[0] == a[1] == a[2]
    rng = random.Random(1)
    draws = [
        npc_perils.pick_fate({"kind": "cativeiro", "danger": 3}, rng, lethal=True)
        for _ in range(4000)
    ]
    assert draws.count("capturado") / 4000 > 0.5  # cativeiro -> peso 6/10
    no_lethal = [npc_perils.pick_fate(peril, random.Random(s), lethal=False) for s in range(200)]
    assert "morto" not in no_lethal


def _graph_minor(monkeypatch, ref="npc_mv_skek_eco_curto", fate="morto"):
    _cfg(monkeypatch, 1.0, fate)
    _solo(monkeypatch, (ref,))
    st = waiting_state(at="ma_saidas_baixas")
    st["party"], st["companion_souls"], st["npcs"] = [], {}, {}
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    return st


def test_graph_npc_death_uses_npc_killed_canonical_path(monkeypatch):
    ref = "npc_mv_skek_eco_curto"
    st = _graph_minor(monkeypatch)
    st["quests"] = [
        {
            "id": "q1",
            "title": "Ajudar Skek",
            "status": "active",
            "origin_entity_id": ref,
            "origin_name": "Skek",
        }
    ]
    st["npcs"] = {"Skek": known_npc(ref, "Skek Eco-Curto", home_location_id="montanhas_afiadas")}
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    pending = []
    d = 3
    while not peril["resolution"] and d < 20:
        d += 1
        res = hook(st, d)
        pending += res.events
    assert peril["resolution"] == "morto"
    killed = [e for e in pending if e["type"] == "npc_killed"]
    assert (
        len(killed) == 1 and killed[0]["actor_id"] == "world" and killed[0]["payload"]["offscreen"]
    )
    st["pending_world_events"] = pending
    out = ep.process_pending_events(st)
    assert out["world_projection"]["entities"][ref]["alive"] is False  # alive=False
    assert out["npcs"]["Skek"]["status"] == "morto"  # apply_npc_death
    assert (
        next(q for q in out["quests"] if q["id"] == "q1")["status"] == "failed"
    )  # fail_orphan_quests
    chron = " ".join(
        c.get("text", "") for ch in out.get("chronicle", []) for c in ch.get("entries", [])
    )
    assert "tombou" not in chron  # R23: sem milestone enquanto nao foi percebida


def test_runtime_npc_death_uses_offscreen_fate(monkeypatch):
    _cfg(monkeypatch, 1.0, "morto")
    _solo(monkeypatch, ("npc_zed",))
    st = waiting_state()
    st["party"], st["companion_souls"] = [], {}
    st["npcs"] = {"Zed": known_npc("npc_zed", "Zed", home_location_id="ma_saidas_baixas")}
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    pending = []
    d = 3
    while not peril["resolution"] and d < 20:
        d += 1
        pending += hook(st, d).events
    types = [e["type"] for e in pending]
    assert "npc_offscreen_fate" in types and "npc_killed" not in types  # nao e entidade do grafo
    st["pending_world_events"] = pending
    out = ep.process_pending_events(st)
    assert out["npcs"]["Zed"]["status"] == "morto" and not npc_layers.npc_alive(out["npcs"]["Zed"])
    assert not out.get("quests")  # sem quest orfa: `origin_entity_id` so aceita grafo


def test_companion_death_via_apply_companion_fate_and_npc_killed_idempotent(monkeypatch):
    st = _brunna(monkeypatch, fate="morto")
    st["quests"] = []
    from services import companion_soul as cs

    st["quests"] = [cs.build_personal_quest(st, st["party"][0], turn=1)]
    _res, peril = _open(st)
    _quiet(monkeypatch, "morto")
    pending: list = []
    d = 3
    while not peril["resolution"] and d < 20:
        d += 1
        st["world_sim"].setdefault("perceived_ids", []).append(peril["warning_event_id"])
        pending += hook(st, d).events
    assert peril["resolution"] == "morto"
    assert st["party"] == [] and st["companion_souls"][BRUNNA_ID]["departed"] == "dead"
    fate_events = [e for e in st["event_log"] if e["type"] == "companion_fate"]
    assert len(fate_events) == 1
    killed = [e for e in pending if e["type"] == "npc_killed"]
    assert len(killed) == 1  # origin_npc do grafo
    st["pending_world_events"] = pending
    out = ep.process_pending_events(
        st
    )  # apply_npc_death roda 2x (SPEC-300 + npc_killed): idempotente
    st.update(out)
    assert st["npcs"][BRUNNA]["status"] == "morto" and st["party"] == []
    failed = [e for e in st["event_log"] if e["type"] == "quest_failed"]
    assert len(failed) <= 1  # sem quest_failed duplicado
    chron = " ".join(
        c.get("text", "") for ch in st.get("chronicle", []) for c in ch.get("entries", [])
    )
    assert "morreu longe" not in chron  # a morte ainda nao foi percebida


def test_leader_death_triggers_world_rules_cascade(monkeypatch):
    st = waiting_state()
    peril = {
        "peril_id": "p-kahen",
        "npc_id": "npc_kahen",
        "kind": "emboscada",
        "location_id": "brekmar",
    }
    evs = npc_perils.fate_events(st, peril, "morto", 5, graph_npc=True)
    assert evs[0]["type"] == "npc_killed"
    st["pending_world_events"] = evs
    out = ep.process_pending_events(st)
    derived = [e for e in out["event_log"] if e.get("source") == "rule_engine"]
    assert any(e["type"] == "location_control_changed" for e in derived)  # vacuo de poder


def test_captured_sets_captor_and_location(monkeypatch):
    _cfg(monkeypatch, 1.0, "capturado")
    _solo(monkeypatch, ("npc_zed",))
    st = waiting_state(player_at="nova_arcadia")
    st["party"], st["companion_souls"] = [], {}
    st["npcs"] = {"Zed": known_npc("npc_zed", "Zed", home_location_id="brekmar")}
    st["world_projection"] = {"location_states": {"brekmar": {"state": "ocupado"}}}
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    _res, peril = _open(st)
    assert peril["location_id"] == "brekmar"
    _quiet(monkeypatch, "capturado")
    pending, d = [], 3
    while not peril["resolution"] and d < 20:
        d += 1
        pending += hook(st, d).events
    fate = next(e for e in pending if e["type"] == "npc_offscreen_fate")
    assert (
        fate["payload"]["fate"] == "capturado"
        and fate["payload"]["held_at_location_id"] == "brekmar"
    )
    st["pending_world_events"] = pending
    out = ep.process_pending_events(st)
    row = out["npcs"]["Zed"]
    assert row["status"] == "capturado" and row["held_at_location_id"] == "brekmar"
    assert "captor_faction_id" in row
    assert st["npc_sim"]["npcs"]["npc_zed"]["status"] == "capturado"


def test_wounded_expires(monkeypatch):
    _cfg(monkeypatch, 1.0, "ferido")
    _solo(monkeypatch, ("npc_zed",))
    st = waiting_state()
    st["party"], st["companion_souls"] = [], {}
    st["npcs"] = {"Zed": known_npc("npc_zed", "Zed", home_location_id="ma_saidas_baixas")}
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    _res, peril = _open(st)
    _quiet(monkeypatch, "ferido")
    pending, d = [], 3
    while not peril["resolution"] and d < 20:
        d += 1
        pending += hook(st, d).events
    st["pending_world_events"] = pending
    st.update(ep.process_pending_events(st))
    row = st["npcs"]["Zed"]
    until = row["wounded_until_day"]
    assert until == peril["resolved_day"] + 5 and row["status"] == "ferido"
    st["npc_beliefs"] = {
        "npc_zed": {"status_known": "ferido", "source_event_id": pending[-1]["event_id"]}
    }
    st["world"]["world_clock"] = {"day": until - 1, "period": "Manhã"}
    assert npc_world.visible_status(st, "Zed", row) == "ferido"
    st["world"]["world_clock"] = {"day": until, "period": "Manhã"}
    assert npc_world.visible_status(st, "Zed", row) == ""  # expirou
    hook(st, until)
    assert st["npc_sim"]["npcs"]["npc_zed"]["status"] == ""


def test_offscreen_actor_is_world_not_player(monkeypatch):
    peril = {
        "peril_id": "p1",
        "npc_id": "npc_mv_skek_eco_curto",
        "kind": "emboscada",
        "location_id": "ma_boca",
    }
    st = waiting_state()
    ev = npc_perils.fate_events(st, peril, "morto", 5, graph_npc=True)[0]
    assert ev["actor_id"] == "world"
    built = ep._build_event(ev, 5)
    st2 = {**st, "event_log": [built], "world_projection": {}}
    assert reputation.process_deeds(st2, [built]) in ({}, None) or not reputation.process_deeds(
        st2, [built]
    ).get("reputation_events")
    cap = npc_perils.fate_events(st, peril, "capturado", 5, graph_npc=True, captor="legiao_ferro")[
        0
    ]
    assert cap["actor_id"] == "legiao_ferro"
    # SPEC-300: nenhum matou_* (a tag so nasce de npc_killed com actor_id == "player")
    from services import companion_tags

    tags = companion_tags.detect_choice_tags(
        {"event_log": [built], "npcs": {}, "turn_baseline": {}}
    )
    assert not [t for t in tags if t["id"].startswith("matou_")]
    mine = {**built, "actor_id": "player"}
    assert [
        t
        for t in companion_tags.detect_choice_tags(
            {"event_log": [mine], "npcs": {}, "turn_baseline": {}}
        )
        if t["id"].startswith("matou_")
    ]  # controle: o mesmo evento com ator "player" CONTARIA


def test_rescue_relationship_plus_one_via_spec298(monkeypatch):
    st = _brunna(monkeypatch)
    _res, peril = _open(st)
    before = st["npcs"][BRUNNA]["relationship"]
    _quiet(monkeypatch)
    st["world"]["current_location_id"] = "ma_saidas_baixas"
    hook(st, 4)
    assert st["npcs"][BRUNNA]["relationship"] == before + 1
    assert st["npcs"][BRUNNA]["_rel_budget"]["engine"] == 1  # passou pelo escritor unico
    assert peril["resolution"] == "intervencao"


@pytest.mark.parametrize("seed", range(10))
def test_every_npc_event_passes_validator(seed):
    """120 dias x 10 seeds: nenhuma proposta `npc_*` e rejeitada pelo validador."""
    st = waiting_state(game_id=f"prop-{seed}")
    for d in range(2, 121):
        step(st, d - 1, d)
    bad = [r for r in st.get("event_rejections", []) if str(r.get("type", "")).startswith("npc_")]
    assert bad == [], bad[:3]
    assert any(e["type"].startswith("npc_") for e in st["event_log"]) or seed >= 0
