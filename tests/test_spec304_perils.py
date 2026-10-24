"""SPEC-304 Etapa 4: exposição, perigo e telegrama (R12-R15)."""

from __future__ import annotations

import copy
import random

import pytest

from services import companion_soul as cs
from services import npc_knowledge, npc_perils, npc_world
from services import world_director as wd
from services import world_perception as wperc
from tests.spec304_helpers import (
    BRUNNA_ID,
    hook,
    known_npc,
    setup_env,
    waiting_state,
)

DANGER4 = "selva_xylos"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")


def _hot(monkeypatch, p=1.0):
    cfg = copy.deepcopy(npc_perils.cfg())
    cfg["BASE_HAZARD"] = {"3": p, "4": p}
    monkeypatch.setattr(npc_perils, "cfg", lambda: cfg)


def _solo(monkeypatch, refs=(BRUNNA_ID,)):
    monkeypatch.setattr(npc_world, "_candidates", lambda state, sim: list(refs))


def _fresh(monkeypatch, **kw):
    """Brunna esperando num local de perigo 3; so ela no elenco; calma inicial do diretor zerada."""
    _solo(monkeypatch)
    st = waiting_state(**kw)
    hook(st, 2)
    st["world_sim"]["calm_until_day"] = 0
    return st


def test_exposure_by_danger_state_and_route():
    st = waiting_state(player_at="brekmar")
    ex = npc_perils.exposure
    assert ex(st, "x", {"location_id": "ma_saidas_baixas"}, 3) == (True, "emboscada", 3)
    assert ex(st, "x", {"location_id": "nova_arcadia"}, 3)[0] is False  # perigo 1, sem estado
    st["world_projection"] = {"location_states": {"nova_arcadia": {"state": "cerco"}}}
    exposed, kind, _d = ex(st, "x", {"location_id": "nova_arcadia"}, 3)
    assert exposed and kind == "cerco"  # estado de crise expoe mesmo com perigo baixo
    st["world_projection"] = {}
    trav = {"location_id": "", "travel_from": "nova_arcadia", "travel_to": DANGER4}
    assert ex(st, "x", trav, 3)[0] is True  # ponta com perigo >= 4
    assert (
        ex(st, "x", {"location_id": "", "travel_from": "nova_arcadia", "travel_to": "brekmar"}, 3)[
            0
        ]
        is False
    )


def test_never_exposed_at_player_location():
    st = waiting_state(player_at="ma_saidas_baixas")
    assert npc_perils.exposure(st, "x", {"location_id": "ma_saidas_baixas"}, 3)[0] is False
    # nem o interior do mesmo lugar
    assert npc_perils.at_player("ma_saidas_baixas", "ma_saidas_baixas")


def test_waiting_at_name_resolved_to_id(monkeypatch):
    _solo(monkeypatch)
    st = waiting_state(at="Saídas Baixas")  # P6: waiting_at guarda o NOME de exibicao
    assert npc_world.resolve_location_ref("Saídas Baixas") == "ma_saidas_baixas"
    hook(st, 2)
    assert st["npc_sim"]["npcs"][BRUNNA_ID]["pos"]["location_id"] == "ma_saidas_baixas"
    assert npc_world.location_of(st, "Brunna Ponte-Alta") == "ma_saidas_baixas"


def test_hazard_seeded_deterministic(monkeypatch):
    _hot(monkeypatch, 0.5)
    outs = []
    for _ in range(2):
        st = _fresh(monkeypatch)
        sim, entry = st["npc_sim"], st["npc_sim"]["npcs"][BRUNNA_ID]
        peril, evs = npc_perils.maybe_open(
            st, sim, BRUNNA_ID, 3, random.Random(7), entry=entry, major=False
        )
        outs.append((peril and peril["peril_id"], [e["event_id"] for e in evs]))
    assert outs[0] == outs[1]
    ids = {
        npc_perils.maybe_open(
            _fresh(monkeypatch),
            {"perils": []},
            BRUNNA_ID,
            3,
            random.Random(s),
            entry={"pos": {"location_id": "ma_saidas_baixas"}, "archetype": "sedentario"},
        )[0]
        is not None
        for s in range(40)
    }
    assert ids == {True, False}  # o sorteio depende do rng, nao de relogio


def test_caps_active_per_npc_cooldown(monkeypatch):
    _hot(monkeypatch)
    st = _fresh(monkeypatch)
    sim, entry = st["npc_sim"], st["npc_sim"]["npcs"][BRUNNA_ID]
    kw = dict(entry=entry, major=False)
    rng = lambda: random.Random(1)  # noqa: E731
    p1, _ = npc_perils.maybe_open(st, sim, BRUNNA_ID, 3, rng(), **kw)
    assert p1 is not None
    assert npc_perils.maybe_open(st, sim, BRUNNA_ID, 3, rng(), **kw)[0] is None  # 1 por NPC
    p1["resolution"] = "ferido"
    entry["last_peril_end_day"] = 3
    assert npc_perils.maybe_open(st, sim, BRUNNA_ID, 10, rng(), **kw)[0] is None  # cooldown 15d
    assert npc_perils.maybe_open(st, sim, BRUNNA_ID, 19, rng(), **kw)[0] is not None
    sim["perils"] = [{"peril_id": f"p{i}", "npc_id": f"n{i}", "resolution": ""} for i in range(3)]
    entry["last_peril_end_day"] = None
    assert npc_perils.maybe_open(st, sim, BRUNNA_ID, 30, rng(), **kw)[0] is None  # teto global 3


def test_major_peril_requires_crisis_slot(monkeypatch):
    _hot(monkeypatch)
    st = _fresh(monkeypatch)
    sim, entry, dsim = st["npc_sim"], st["npc_sim"]["npcs"][BRUNNA_ID], st["world_sim"]
    kw = dict(entry=entry, major=True, dsim=dsim)
    # orcamento cheio (2 crises ativas): sem vaga -> o perigo maior NAO abre
    dsim["crises"] = [
        {
            "crisis_id": f"c{i}",
            "kind": "guerra",
            "region_id": f"r{i}",
            "start_day": 1,
            "end_day": None,
        }
        for i in range(2)
    ]
    assert npc_perils.maybe_open(st, sim, BRUNNA_ID, 3, random.Random(1), **kw)[0] is None
    dsim["crises"] = []
    peril, evs = npc_perils.maybe_open(st, sim, BRUNNA_ID, 3, random.Random(1), **kw)
    assert peril and peril["major"] and peril["crisis_id"]
    assert len(wd.announced_crises(dsim)) == 1  # a vaga entra no orcamento ja no aviso
    assert not npc_perils.try_slot(dsim, peril, 4)  # antes de earliest_day nao abre
    assert npc_perils.try_slot(dsim, peril, peril["earliest_day"])
    rec = wd.active_crises(dsim)[0]
    assert rec["kind"] == wd.NPC_PERIL_KIND and rec["start_day"] == peril["earliest_day"]
    npc_perils.end_slot(dsim, peril, 9, "recuperou")
    assert not wd.active_crises(dsim)
    assert not dsim.get("recovery_until_day")  # nao cria recuperacao nem cooldown de regiao
    # perigo MENOR nao toca o diretor
    dsim["crises"] = []
    st2 = _fresh(monkeypatch)
    p2, _ = npc_perils.maybe_open(
        st2,
        st2["npc_sim"],
        BRUNNA_ID,
        3,
        random.Random(1),
        entry=st2["npc_sim"]["npcs"][BRUNNA_ID],
        major=False,
        dsim=st2["world_sim"],
    )
    assert p2 and not p2["crisis_id"] and not st2["world_sim"].get("crises")


def test_leader_death_gap():
    sim = {"last_leader_death_day": 50}
    peril = {"leader": True, "major": False, "deadline_day": 70}
    assert not npc_perils.lethal_allowed(peril, sim, 70, True)
    assert npc_perils.lethal_allowed(peril, sim, 110, True)
    assert npc_perils.lethal_allowed({"leader": False, "major": False}, sim, 51, True)
    assert not npc_perils.lethal_allowed(
        {"major": True, "perceived_day": None, "deadline_day": 9}, {}, 9, True
    )


def test_warning_emitted_same_day_with_location_id(monkeypatch):
    _hot(monkeypatch)
    st = _fresh(monkeypatch)
    res = hook(st, 3)
    ev = next(e for e in res.events if e["type"] == "npc_peril_warning")
    pl = ev["payload"]
    assert ev["target_id"] == BRUNNA_ID and ev["source"] == "engine" and ev["actor_id"] == "world"
    assert pl["location_id"] == "ma_saidas_baixas" and pl["region_id"] == "montanhas_afiadas"
    assert pl["opened_day"] == 3 and pl["earliest_day"] == 5 and pl["deadline_day"] in (6, 7, 8)
    assert pl["channel"] == "pedido_de_ajuda"
    item = next(i for i in res.digest if i["kind"] == "npc_perigo")
    assert item["subject_id"] == ev["event_id"] and item["location_id"] == "ma_saidas_baixas"
    # P10: evento do motor sem local valido nao "acontece" ao lado do jogador
    st["world"]["current_location_id"] = "brekmar"
    assert npc_knowledge._event_origin(st, ev) == "ma_saidas_baixas"
    assert (
        npc_knowledge._event_origin(st, {**ev, "payload": {"offscreen": True}, "target_id": "x"})
        == ""
    )


def test_warning_propagates_via_spec215(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    _hot(monkeypatch)
    st = _fresh(monkeypatch)
    res = hook(st, 3)
    ev = next(e for e in res.events if e["type"] == "npc_peril_warning")
    gev = {**ev, "turn": st["world"]["turn_count"]}
    st["event_log"] = [gev]
    assert "npc_peril_warning" in npc_knowledge.SUBJECT_PARAMS and npc_knowledge._witnessable(gev)
    out = npc_knowledge.turn_updates(st)
    heard = out["location_heard"]
    assert ev["event_id"] in heard.get("ma_saidas_baixas", [])  # `location_heard` do destino


def test_help_request_delivered_to_player_location_before_deadline(monkeypatch):
    _hot(monkeypatch)
    st = _fresh(monkeypatch, player_at="nova_arcadia")
    res = hook(st, 3)
    item = next(i for i in res.digest if i["template_id"] == "npc_perigo.pedido_de_ajuda")
    peril = st["npc_sim"]["perils"][0]
    delivery = item["params"]["delivery_day"]
    assert peril["opened_day"] <= delivery <= peril["deadline_day"] - 1
    far = {**st, "world": {**st["world"], "world_clock": {"day": delivery - 1, "period": "Manhã"}}}
    if delivery > peril["opened_day"]:
        assert wperc.perceivable(far, [item]) == []
    due = {**st, "world": {**st["world"], "world_clock": {"day": delivery, "period": "Manhã"}}}
    assert wperc.perceivable(due, [item]) == [item]  # o mensageiro acha o jogador onde ele estiver
    text = wperc.render(due, item)
    assert "Saídas Baixas" in text and "Brunna" in text


def test_companion_telegraph_calls_spec300_interface(monkeypatch):
    _hot(monkeypatch)
    calls = []
    real = cs.telegraph_companion_danger

    def spy(state, cid, kind, day):
        calls.append((cid, kind, day))
        return real(state, cid, kind, day)

    monkeypatch.setattr(cs, "telegraph_companion_danger", spy)
    st = _fresh(monkeypatch)
    hook(st, 3)
    assert calls == [(BRUNNA_ID, "pedido_de_ajuda", 3)]
    assert st["companion_souls"][BRUNNA_ID]["telegraphs"][-1]["kind"] == "pedido_de_ajuda"
    # NPC nao-companheiro nao chama a interface
    calls.clear()
    st2 = waiting_state()
    st2["party"] = []
    st2["npcs"]["Zed"] = known_npc("npc_zed", "Zed", home_location_id="ma_saidas_baixas")
    _solo(monkeypatch, refs=("npc_zed",))
    hook(st2, 2)
    st2["world_sim"]["calm_until_day"] = 0
    hook(st2, 3)
    assert calls == []
