"""SPEC-312: correcoes da revisao (P2-2 segredos, P2-3 vida util, P2-4 save, P2-5 tamanho, P2-6/7)."""

from __future__ import annotations

import os

import pytest

from services import graph_resolver as gr
from services import rumors
from tests.spec312_helpers import base_state, make_rumor, run_hook, walk


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_RUMORS", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _lore():
    return {k: s for k, s in rumors.load_seeds().items() if s["family"] == "lore"}


def test_vibora_is_false_and_no_seed_names_a_secret_faction():
    seeds = _lore()
    assert seeds["rumor_a_vibora_e_uma_crianca"]["truth"] is False
    ents = gr.load_entities()
    for sid, s in seeds.items():
        if s.get("secret_id"):
            assert not [e for e in s["entities"] if ents[e]["type"] == "faction"], sid
    assert "mao_sombria" not in str([s["entities"] for s in seeds.values() if s.get("secret_id")])


CURATED = {
    "rumor_valerius_nao_come_nem_dorme",
    "rumor_grum_guarda_algo_no_barril_de_cerveja_azeda",
    "rumor_a_vibora_e_uma_crianca",
    "rumor_valerius_e_o_arauto_da_nevoa_sao_o_mesmo_ser",
    "rumor_o_rei_tem_medo_de_algo",
    "rumor_a_praga_de_ferro_nao_veio_das_minas",
}


def test_secret_seeds_are_blocked_until_revealed_and_never_quest_eligible(monkeypatch):
    seeds = _lore()
    assert CURATED <= {k for k, s in seeds.items() if s.get("secret_id")}
    import services.memory_provenance as mp

    for sid, s in seeds.items():
        if not s.get("secret_id"):
            continue
        assert s["quest_eligible"] is False, sid  # confirmar revelaria o segredo
        region = s["regions"][0]
        got = {c["seed_id"] for c, _w in rumors.candidates(base_state(), {}, region, 10)}
        assert sid not in got, sid
        monkeypatch.setattr(mp, "accepted_secret_ids", lambda state, sec=s["secret_id"]: {sec})
        got = {c["seed_id"] for c, _w in rumors.candidates(base_state(), {}, region, 10)}
        assert sid in got, sid
        monkeypatch.undo()
        monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
        monkeypatch.setenv("RPG_RUMORS", "on")
    # e nunca investigavel enquanto bloqueado
    sim: dict = {}
    make_rumor(sim, "rumor_a_vibora_e_uma_crianca", perceived=5)
    assert rumors.investigable(base_state(6, world_sim=sim), 6) == []


def _row(n, expires, perceived, **kw):
    return {
        "rumor_id": f"r{n}",
        "seed_id": kw.pop("seed_id", f"s{n}"),
        "family": kw.pop("family", "lore"),
        "born_day": n,
        "expires_day": expires,
        "perceived_day": perceived,
        **kw,
    }


def test_investigable_instance_stays_resolvable_for_the_horizon():
    keep = _row(1, 100, 95, quest_eligible=True)
    sim = {"rumors": [keep]}
    rumors._cap_ledger(sim, 100 + rumors.INVESTIGABLE_HORIZON_DAYS)
    assert rumors.truth_of({"world_sim": sim}, "r1") is not None
    rumors._cap_ledger(sim, 100 + rumors.INVESTIGABLE_HORIZON_DAYS + 1)
    assert sim["rumors"] == []
    # nao elegivel a quest: some cedo
    sim2 = {"rumors": [_row(2, 100, 95, quest_eligible=False)]}
    rumors._cap_ledger(sim2, 100 + rumors.STALE_PERCEIVED_DAYS + 1)
    assert sim2["rumors"] == []
    # resolvido: deixa de ser protegido
    sim3 = {"rumors": [_row(3, 100, 95, quest_eligible=True, resolution="desmentido")]}
    rumors._cap_ledger(sim3, 100 + rumors.STALE_PERCEIVED_DAYS + 1)
    assert sim3["rumors"] == []


def test_cap_never_evicts_investigable_rows():
    cap = rumors.const("RUMOR_LEDGER_MAX")
    rows = [_row(n, 100, 95, quest_eligible=True) for n in range(cap + 5)]
    sim = {"rumors": rows}
    rumors._cap_ledger(sim, 102)
    assert len(sim["rumors"]) == cap + 5  # protegidos: o teto e brando para eles


def test_never_again_only_lore_and_bounded():
    sim = {
        "rumors": [
            _row(1, 10, 5, family="narrador", seed_id="narrador:abc"),
            _row(2, 10, 5, family="lore", seed_id="rumor_x"),
            _row(3, 10, 5, family="avistamento", seed_id="rumor_avist_y"),
        ]
    }
    rumors._cap_ledger(sim, 500)
    last = sim["rumor_seed_last_born"]
    assert last.get(rumors._k("rumor_x")) == rumors.NEVER_AGAIN
    assert rumors._k("narrador:abc") not in last and rumors._k("rumor_avist_y") not in last
    assert all(len(k) == 8 for k in last)
    # 365 dias parado: o mapa de cooldown tem no maximo 40 NEVER_AGAIN (so lore) + janela
    s, _ = walk(365)
    never = [v for v in s["rumor_seed_last_born"].values() if v == rumors.NEVER_AGAIN]
    assert len(never) <= len(_lore())


def test_shadow_applies_cooldown_like_on(monkeypatch):
    monkeypatch.setenv("RPG_RUMORS", "shadow")
    sim: dict = {}
    for d in range(1, 60):
        run_hook(sim, d)
    keys_shadow = set(sim["rumor_seed_last_born"])
    assert keys_shadow  # cooldown gravado
    assert not sim.get("rumors") and not sim.get("rumor_born_total")


def test_born_total_is_cumulative_even_after_ledger_pruning():
    sim, items = walk(120)
    assert sim["rumor_born_total"] == len(items) > len(sim["rumors"])
    from playtest.telemetry import _rumor_summary

    assert _rumor_summary(sim)["born"] == len(items)


def test_world_sim_rumors_survive_save_and_load():
    import persistence

    sim: dict = {}
    r = make_rumor(
        sim,
        "rumor_o_pantano_esta_crescendo",
        region="pantano_melancolia",
        loc="pantano_melancolia",
        day=5,
        perceived=5,
    )
    sim["region_presence"] = {"pantano_melancolia": 5}
    sim["rumor_seed_last_born"] = {rumors._k("rumor_o_pantano_esta_crescendo"): rumors.NEVER_AGAIN}
    sim["rumor_born_total"] = 3
    world = {
        "current_location_id": "pantano_melancolia",
        "world_clock": {"day": 5, "period": "Manhã"},
        "turn_count": 5,
        "news": [
            {
                "day": 5,
                "period": "Manhã",
                "location_id": "x",
                "location_name": "X",
                "text": "dizem",
                "source": "world_engine",
                "turn": 5,
                "kind": "rumor",
                "rumor_id": r["subject_id"],
                "expires_day": 15,
            }
        ],
    }
    state = base_state(5, "pantano_melancolia", world_sim=sim, world=world)
    state["game_id"] = "spec312-roundtrip"
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(
        os.path.join(persistence.SAVES_DIR, "spec312-roundtrip.json")
    )
    assert loaded["world_sim"] == sim
    assert loaded["world"]["news"][0] == world["news"][0]
    assert rumors.truth_of(loaded, r["subject_id"]) is True
