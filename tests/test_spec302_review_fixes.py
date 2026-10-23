"""SPEC-302: correcoes da revisao Sol (P1-1, P2-1..P2-5)."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from agents import world_simulator as wsim
from services import world_engine as we
from services import world_pressures as wp
from services.world_validators import validate_proposal
from tests.spec302_helpers import make_state, tick


@pytest.fixture(autouse=True)
def _mode_on(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")


@pytest.mark.parametrize("relation", ["neutral", "allied_with"])
def test_llm_cannot_propose_peace_or_alliance(relation):
    prop = {
        "type": "faction_relation_changed",
        "target_id": "legiao_ferro",
        "payload": {"other_faction_id": "filhos_chama_azul", "relation": relation},
    }
    st = make_state()
    res = validate_proposal(prop, st)
    assert not res.ok and "motor" in res.reason
    assert validate_proposal({**prop, "source": "engine"}, st).ok
    # a LLM ainda pode propor hostilidade (comportamento pre-existente)
    enemy = {**prop, "payload": {**prop["payload"], "relation": "enemy_of"}}
    assert validate_proposal(enemy, st).ok


def test_old_danger_override_decays_in_on_mode():
    from agents import storyteller

    world = {
        "world_clock": {"day": 3, "period": "Manhã"},
        "current_location_id": "nova_arcadia",
        "danger_overrides": {"nova_arcadia": 2},
        "danger_shift_turns": {"nova_arcadia": 0},
        "turn_count": 50,
    }
    st = make_state(world=world)
    after = {**world, "world_clock": {"day": 4, "period": "Manhã"}}
    new_world, _f, _t = storyteller._world_tick(st, world, after, st["factions"], {})
    assert "nova_arcadia" not in (new_world.get("danger_overrides") or {})


def test_api_blocked_routes_only_known_locations():
    import api

    w = {
        "current_location_id": "nova_arcadia",
        "visited": ["nova_arcadia"],
        "world_clock": {"day": 1, "period": "Manhã"},
    }
    proj = {
        "blocked_routes": [
            {"a": "nova_arcadia", "b": "pantano_melancolia"},
            {"a": "skallgard", "b": "montanhas_afiadas"},
        ]
    }
    block = api._world_block(w, proj, [], {})
    assert block["blocked_routes"] == [{"a": "nova_arcadia", "b": "pantano_melancolia"}]


def test_stale_world_sim_after_long_off_is_reinitialized(monkeypatch):
    st = make_state("stale")
    tick(st, 1, 6)
    old_crises = [
        {"crisis_id": "x", "kind": "fome", "region_id": "brekmar", "start_day": 4, "end_day": None}
    ]
    st["world_sim"]["crises"] = old_crises
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    tick(st, 6, 80)  # motor desligado: nada roda
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    res = tick(st, 80, 81)
    assert res.days_ticked == 1
    assert res.world_sim["enabled_from_day"] == 80
    assert not [c for c in res.world_sim["crises"] if c["crisis_id"] == "x"]


def test_narrator_prompt_has_human_message(monkeypatch):
    seen = {}

    class _LLM:
        def with_structured_output(self, model):
            class _I:
                def invoke(self, msgs):
                    seen["msgs"] = msgs
                    return model(text="Os preços do pão subiram.")

            return _I()

    monkeypatch.setattr(wsim, "get_llm", lambda **kw: _LLM())
    from services.world_director import digest_item

    st = {
        "world": {"current_location_id": "nova_arcadia"},
        "factions": [],
        "faction_intel": {},
        "npcs": {},
    }
    item = digest_item("g", 1, "sinal", "nova_arcadia", "nova_arcadia", "fome.sinal.preco", {})
    wsim.narrate_day(st, [item])
    assert any(isinstance(m, HumanMessage) and "FATO:" in m.content for m in seen["msgs"])


def test_remote_regions_do_not_inflate_crisis_rate():
    weights = wp.get_config()["surge_weight"]
    assert weights["ophidia"] == 1.0 and weights["costa_negra"] == 1.0
    assert set(weights) == set(wp.region_ids()) and we.DEFAULT_MODE == "on"
