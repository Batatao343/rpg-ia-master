"""SPEC-304 Etapa 3: troca de lado (R10, R11) e modo shadow (R29)."""

from __future__ import annotations

import copy

import pytest

from services import event_processor as ep
from services import npc_perils, npc_world
from services.world_validators import validate_proposal
from tests.spec304_helpers import (
    hook,
    known_npc,
    setup_env,
    waiting_state,
)

MINA = "npc_mv_mina_sete_taxas"  # casa em brekmar; faccao so no grafo (tres_sindicatos_comercio)
JAX = "npc_mv_jax_corda_seca"  # casa em brekmar; grupos_piratas_rivais (faccao simulada)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    setup_env(monkeypatch, "on")
    monkeypatch.setattr("services.npc_perils.maybe_open", lambda *a, **k: (None, []))


def _p_one(monkeypatch):
    real = npc_perils.cfg()
    cfg = copy.deepcopy(real)
    for c in cfg["defection_causes"]:
        c["p"] = 1.0
    monkeypatch.setattr(npc_perils, "cfg", lambda: cfg)


def _control(target="brekmar", new="legiao_ferro") -> dict:
    return {
        "type": "location_control_changed",
        "actor_id": "engine",
        "target_id": target,
        "payload": {"new_controller_id": new},
        "event_id": "ctrl-1",
        "source": "engine",
    }


def _plain() -> dict:
    st = waiting_state()
    st["party"], st["companion_souls"], st["npcs"] = [], {}, {}
    return st


def test_defection_on_home_control_change(monkeypatch):
    _p_one(monkeypatch)
    st = _plain()
    hook(st, 2)
    res = hook(st, 3, events=[_control()])
    defects = [e for e in res.events if e["type"] == "npc_defected"]
    assert len(defects) == 1
    ev = defects[0]
    assert ev["target_id"] in (JAX, "npc_mv_varo_dois_portos")
    assert ev["payload"]["to_faction_id"] == "legiao_ferro" and ev["payload"]["cause"] == (
        "location_control_changed"
    )
    assert ev["payload"]["from_faction_id"] != "legiao_ferro" and ev["actor_id"] == "world"
    assert [i for i in res.digest if i["template_id"] == "npc_lado.mudou"]


def test_trait_multiplier_and_blocker_zero(monkeypatch):
    assert npc_world._trait_mult({"hidden_traits": ["lingua_dupla"]}) == 2.0
    assert npc_world._trait_mult({"revealed_traits": ["guarda_subornavel", "lingua_dupla"]}) == 4.0
    assert npc_world._trait_mult({"hidden_traits": ["honesto_demais", "lingua_dupla"]}) == 0.0
    assert npc_world._trait_mult({}) == 1.0
    _p_one(monkeypatch)
    st = _plain()
    for ref, name in ((JAX, "Jax"), ("npc_mv_varo_dois_portos", "Varo")):
        st["npcs"][name] = known_npc(
            ref, name, home_location_id="brekmar", hidden_traits=["leal_a_familia"]
        )
    hook(st, 2)
    res = hook(st, 3, events=[_control()])
    assert not [e for e in res.events if e["type"] == "npc_defected"]


def test_leader_never_defects(monkeypatch):
    _p_one(monkeypatch)
    st = _plain()
    hook(st, 2)
    leader_home = st["npc_sim"]["npcs"]["npc_durgrim_ultimo_martelo"]["home"]
    res = hook(st, 3, events=[_control(target=leader_home)])
    assert not [e for e in res.events if e["target_id"] == "npc_durgrim_ultimo_martelo"]
    assert npc_world.is_leader("npc_durgrim_ultimo_martelo")


def test_party_member_never_defects(monkeypatch):
    _p_one(monkeypatch)
    st = waiting_state(at="brekmar")
    hook(st, 2)
    res = hook(st, 3, events=[_control(target="brekmar")])
    assert not [e for e in res.events if e["target_id"] == "npc_mv_brunna_ponte_alta"]


def test_max_one_defection_per_day(monkeypatch):
    _p_one(monkeypatch)
    st = _plain()
    hook(st, 2)
    res = hook(st, 3, events=[_control()])
    assert sum(1 for e in res.events if e["type"] == "npc_defected") == 1  # Mina e Jax: so 1


def test_npc_defected_engine_only():
    base = {
        "type": "npc_defected",
        "actor_id": "world",
        "target_id": JAX,
        "payload": {"from_faction_id": "grupos_piratas_rivais", "to_faction_id": "legiao_ferro"},
    }
    state = {"npcs": {}, "world": {}, "event_log": []}
    assert not validate_proposal({**base, "source": "storyteller"}, state).ok
    assert not validate_proposal(base, state).ok  # sem source (proposta da LLM)
    assert validate_proposal({**base, "source": "engine"}, state).ok
    bad = {**base, "payload": {**base["payload"], "to_faction_id": "faccao_inventada"}}
    assert not validate_proposal({**bad, "source": "engine"}, state).ok
    lead = {**base, "target_id": "npc_durgrim_ultimo_martelo"}
    assert not validate_proposal({**lead, "source": "engine"}, state).ok  # lider nao deserta


def test_apply_event_sets_npc_affiliation():
    proj = ep.apply_event(
        {
            "type": "npc_defected",
            "target_id": JAX,
            "payload": {"to_faction_id": "legiao_ferro"},
            "event_id": "e1",
        },
        {},
    )
    assert proj["npc_affiliations"][JAX] == "legiao_ferro"


def test_npc_faction_resolution_order():
    st = _plain()
    assert npc_world.npc_faction(st, JAX) == "grupos_piratas_rivais"  # componente do grafo
    assert npc_world.npc_faction(st, MINA) == "tres_sindicatos_comercio"  # faccao so do grafo
    assert npc_world.npc_faction(st, "npc_durgrim_ultimo_martelo") == "ultimos_anoes_reino"  # leads
    st["npcs"]["Jax"] = known_npc(JAX, "Jax", faction="legiao_ferro")
    assert npc_world.npc_faction(st, JAX) == "legiao_ferro"  # ficha vence o grafo
    st["world_projection"] = {"npc_affiliations": {JAX: "poder_kahen"}}
    assert npc_world.npc_faction(st, JAX) == "poder_kahen"  # override da projection vence tudo
    assert npc_world.npc_faction(st, "npc_inexistente") == ""


def test_shadow_writes_shadow_key_only(monkeypatch):
    setup_env(monkeypatch, "shadow")
    _p_one(monkeypatch)
    st = _plain()
    hook(st, 2)
    res = hook(st, 3, events=[_control()])
    assert res.events == [] and res.digest == []
    assert set(res.state_patch) == {"npc_sim_shadow"}
    assert "npc_sim" not in st or not st["npc_sim"]
    assert st["npc_sim_shadow"]["roster"] and not st.get("npc_beliefs")
