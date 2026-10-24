"""SPEC-304 Etapa 2: agenda, viagem, fuga de crise e posição na cena (R3-R9)."""

from __future__ import annotations

import copy
import json
import math

import pytest

from services import npc_world, world_distance
from services import world_pressures as wp
from tests.spec304_helpers import (
    hook,
    known_npc,
    setup_env,
    waiting_state,
)

MINA = "npc_mv_mina_sete_taxas"  # sedentario, casa em brekmar
GROTH = "npc_groth_algema_fria"  # mercador_itinerante (lider)
DURGRIM = "npc_durgrim_ultimo_martelo"  # lider_residente


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")
    # perigo desligado: aqui so agenda/fuga
    monkeypatch.setattr("services.npc_perils.maybe_open", lambda *a, **k: (None, []))


def _flee_always(monkeypatch) -> None:
    from services import npc_perils

    cfg = copy.deepcopy(npc_perils.cfg())
    cfg["constants"]["P_FLEE"] = 1.0
    monkeypatch.setattr(npc_perils, "cfg", lambda: cfg)


def _plain() -> dict:
    st = waiting_state()
    st["party"] = []
    st["companion_souls"] = {}
    st["npcs"] = {}
    return st


def _fast(monkeypatch, p_leave=1.0, stay=(2, 2), archetypes=("mercador_itinerante",)):
    real = npc_world._agendas()
    cfg = copy.deepcopy(real)
    for a in archetypes:
        cfg["archetypes"][a]["p_leave"] = p_leave
        cfg["archetypes"][a]["stay_days"] = list(stay)
    monkeypatch.setattr(npc_world, "_agendas", lambda: cfg)


def _pos(st, ref):
    return st["npc_sim"]["npcs"][ref]["pos"]


def test_sedentary_never_moves():
    st = _plain()
    for d in range(2, 61):
        hook(st, d)
    entry = st["npc_sim"]["npcs"][MINA]
    assert entry["archetype"] == "sedentario"
    assert _pos(st, MINA)["location_id"] == entry["home"] and entry["home"]


def test_itinerant_leaves_and_returns_within_stay_days(monkeypatch):
    _fast(monkeypatch)
    st = _plain()
    away, trips = None, []
    for d in range(2, 80):
        hook(st, d)
        entry = st["npc_sim"]["npcs"][GROTH]
        home = entry["home"]
        if entry["pos"].get("arrive_day") is not None or entry["pos"]["location_id"] != home:
            away = away if away is not None else d
        elif away is not None:
            trips.append(d - away)
            away = None
    assert trips, "o mercador deveria ter saido e voltado"
    assert all(t <= 2 + 2 * 6 for t in trips)  # estadia 2d + ida e volta


def test_travel_duration_from_world_distance():
    st = _plain()
    hook(st, 2)
    entry = st["npc_sim"]["npcs"][GROTH]
    home = entry["home"]
    dst = next(
        lid
        for lid in sorted(wp._map_index()[0])
        if world_distance.travel_periods(home, lid)
        and lid != home
        and world_distance.travel_periods(home, lid) >= 6
    )
    import random

    ok = npc_world._start_trip(entry, dst, 10, random.Random(1), stay=[2, 2])
    periods = world_distance.travel_periods(home, dst)
    assert ok and entry["pos"]["arrive_day"] == 10 + math.ceil(periods / 5)
    assert entry["pos"]["location_id"] == ""  # em viagem: nao esta em lugar nenhum


def test_travel_avoids_blocked_route():
    st = _plain()
    hook(st, 2)
    entry = st["npc_sim"]["npcs"][GROTH]
    arch = npc_world._agendas()["archetypes"]["mercador_itinerante"]
    cands = npc_world._route_candidates(st, entry, GROTH, arch, st["world_projection"])
    assert cands
    victim = cands[0]
    cur = entry["pos"]["location_id"]
    proj = {"blocked_routes": [{"a": cur, "b": victim}]}
    again = npc_world._route_candidates(st, entry, GROTH, arch, proj)
    assert victim not in again and set(again) < set(cands)
    proj2 = {"location_states": {victim: {"state": "cerco"}}}
    assert victim not in npc_world._route_candidates(st, entry, GROTH, arch, proj2)


def test_refugee_flees_siege_and_returns_after_calm(monkeypatch):
    _flee_always(monkeypatch)
    st = _plain()
    hook(st, 2)
    home = st["npc_sim"]["npcs"][MINA]["home"]
    st["world_projection"]["location_states"] = {home: {"state": "cerco", "severity": 2}}
    for d in range(3, 12):
        hook(st, d)
    pos = _pos(st, MINA)
    assert pos.get("refugee_from") == home
    assert wp.region_of(pos.get("location_id") or pos["travel_to"]) != wp.region_of(home)
    st["world_projection"]["location_states"] = {}  # cerco levantado
    for d in range(12, 40):
        hook(st, d)
    pos = _pos(st, MINA)
    assert pos["location_id"] == home and not pos.get("refugee_from")


def test_leader_residente_does_not_flee(monkeypatch):
    _flee_always(monkeypatch)
    st = _plain()
    hook(st, 2)
    home = st["npc_sim"]["npcs"][DURGRIM]["home"]
    st["world_projection"]["location_states"] = {home: {"state": "cerco", "severity": 3}}
    for d in range(3, 30):
        hook(st, d)
        assert not _pos(st, DURGRIM).get("refugee_from")


def test_archetype_from_role_closed_table():
    st = _plain()
    st["npcs"] = {
        "A": known_npc("npc_a", "A", role="mercadora de especiarias"),
        "B": known_npc("npc_b", "B", role="Guarda do portão"),
        "C": known_npc("npc_c", "C", role="sacerdotisa errante"),
        "D": known_npc("npc_d", "D", role="mensageiro do rei"),
        "E": known_npc("npc_e", "E", role="bardo sem rumo"),
    }
    got = {r: npc_world.archetype_for(st, r) for r in ("npc_a", "npc_b", "npc_c", "npc_d", "npc_e")}
    assert got == {
        "npc_a": "mercador_itinerante",
        "npc_b": "patrulheiro",
        "npc_c": "peregrino",
        "npc_d": "mensageiro",
        "npc_e": "sedentario",
    }


def _scene_state(pos_loc: str, travelling: bool = False) -> dict:
    st = _plain()
    st["world"]["current_location_id"] = "nova_arcadia"
    st["npcs"] = {
        "Zed": known_npc("npc_zed", "Zed", home_location_id="nova_arcadia", in_scene=True)
    }
    entry = {"archetype": "sedentario", "home": "nova_arcadia", "frozen": False}
    entry["pos"] = (
        {"location_id": "", "travel_to": pos_loc, "arrive_day": 9, "since_day": 2}
        if travelling
        else {"location_id": pos_loc, "since_day": 2, "arrive_day": None}
    )
    st["npc_sim"] = {"version": 1, "npcs": {"npc_zed": entry}, "perils": [], "roster": ["npc_zed"]}
    return st


def test_npcs_in_scene_uses_location_of():
    from services.npc_layers import npcs_in_scene

    assert npcs_in_scene(_scene_state("nova_arcadia")) == ["Zed"]
    assert npcs_in_scene(_scene_state("brekmar")) == []  # tem casa aqui, mas esta em brekmar
    assert npcs_in_scene(_scene_state("brekmar", travelling=True)) == []


def test_npcs_for_context_hides_absent_npc():
    from services.npc_layers import npcs_for_context

    assert npcs_for_context(_scene_state("nova_arcadia")) == ["Zed"]
    away = _scene_state("brekmar")
    away["npcs"]["Zed"]["in_scene"] = False
    assert npcs_for_context(away) == []  # casa = aqui, mas a posicao simulada manda
    trav = _scene_state("brekmar", travelling=True)
    trav["npcs"]["Zed"]["in_scene"] = False
    assert npcs_for_context(trav) == []


def test_residents_uses_location_of(monkeypatch):
    from services import npc_knowledge

    st = _scene_state("brekmar")
    st["npcs"]["Zed"]["in_scene"] = False
    assert npc_knowledge._residents(st, "brekmar") == [npc_knowledge.holder_id(st, "Zed")]
    assert npc_knowledge._residents(st, "nova_arcadia") == []  # casa, mas ele nao esta la
    monkeypatch.setenv("RPG_NPC_WORLD", "off")
    assert npc_knowledge._residents(st, "nova_arcadia") == [npc_knowledge.holder_id(st, "Zed")]


def test_storyteller_does_not_teleport_absent_npc():
    from agents import storyteller

    st = _scene_state("brekmar")
    st["npcs"]["Zed"]["in_scene"] = False
    out = storyteller._with_new_npc(
        st["npcs"], "Zed", "Nova Arcadia", "Zed aparece.", home_id="nova_arcadia", state=st
    )
    assert out["Zed"]["in_scene"] is False and out["Zed"]["home_location_id"] == "nova_arcadia"
    here = _scene_state("nova_arcadia")
    here["npcs"]["Zed"]["in_scene"] = False
    out2 = storyteller._with_new_npc(
        here["npcs"], "Zed", "Nova Arcadia", "Zed aparece.", home_id="nova_arcadia", state=here
    )
    assert out2["Zed"]["in_scene"] is True
    # capturado e viajando tambem bloqueiam
    cap = _scene_state("nova_arcadia")
    cap["npcs"]["Zed"].update(in_scene=False, status="capturado")
    out3 = storyteller._with_new_npc(
        cap["npcs"], "Zed", "Nova Arcadia", "x", home_id="nova_arcadia", state=cap
    )
    assert out3["Zed"]["in_scene"] is False


def test_storyteller_never_revives_dead_graph_npc(monkeypatch):
    from agents import storyteller

    def boom(*a, **k):
        raise AssertionError("nao deveria gerar/ressuscitar NPC morto")

    monkeypatch.setattr(storyteller, "generate_new_npc", boom)
    st = _plain()
    st["world_projection"] = {"entities": {"npc_comandante_thrace": {"alive": False}}}
    out = storyteller._with_new_npc(
        {}, "Comandante Thrace", "Nova Arcadia", "Thrace surge.", home_id="nova_arcadia", state=st
    )
    assert out == {}


def test_absence_digest_on_arrival_home(monkeypatch):
    monkeypatch.setattr(npc_world, "_step_position", lambda *a, **k: None)  # sem agenda neste teste
    st = _plain()
    st["npcs"] = {
        "Zed": known_npc("npc_zed", "Zed", home_location_id="brekmar", role="mercador itinerante")
    }
    st["world"]["current_location_id"] = "nova_arcadia"
    hook(st, 2)
    entry = st["npc_sim"]["npcs"]["npc_zed"]
    entry["pos"] = {"location_id": "nova_arcadia", "since_day": 2, "arrive_day": None}
    st["world"]["current_location_id"] = "brekmar"  # o jogador chega a casa do NPC
    res = hook(st, 3)
    items = [i for i in res.digest if i["kind"] == "npc_ausente"]
    assert len(items) == 1 and items[0]["template_id"] == "npc_ausente.sabido"
    assert items[0]["params"]["destino"] == "nova_arcadia"
    again = hook(st, 4)
    assert not [i for i in again.digest if i["kind"] == "npc_ausente"]  # uma vez por saida
    # mensageiro nao conta pra onde foi
    st["npc_sim"]["npcs"]["npc_zed"].update(archetype="mensageiro", absence_noted_since=None)
    st["npc_sim"]["npcs"]["npc_zed"]["pos"]["since_day"] = 5
    res3 = hook(st, 5)
    items3 = [i for i in res3.digest if i["kind"] == "npc_ausente"]
    assert items3 and items3[0]["template_id"] == "npc_ausente.ignorado"


def test_same_seed_same_positions(monkeypatch):
    _fast(
        monkeypatch,
        archetypes=("mercador_itinerante", "patrulheiro", "peregrino", "mensageiro"),
        p_leave=0.5,
    )
    a, b = _plain(), _plain()
    for d in range(2, 40):
        hook(a, d)
        hook(b, d)
    assert json.dumps(a["npc_sim"], sort_keys=True) == json.dumps(b["npc_sim"], sort_keys=True)


def test_independent_of_player(monkeypatch):
    _fast(monkeypatch, p_leave=0.5)
    a, b = _plain(), _plain()
    a["player"] = {"name": "H", "level": 1, "gold": 0}
    b["player"] = {"name": "H", "level": 20, "gold": 99999, "inventory": ["espada"]}
    for d in range(2, 30):
        hook(a, d)
        hook(b, d)
    assert json.dumps(a["npc_sim"], sort_keys=True) == json.dumps(b["npc_sim"], sort_keys=True)
