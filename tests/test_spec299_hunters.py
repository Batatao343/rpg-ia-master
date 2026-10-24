"""SPEC-299 etapa 8 — caçadores de recompensa via ``check_encounter``."""

from __future__ import annotations

import pytest

import world_utils
from services import law
from services.combat_origin import from_encounter, normalize
from tests.spec299_helpers import base_state, with_clock


@pytest.fixture(autouse=True)
def _law_on(monkeypatch):
    monkeypatch.setenv("RPG_LAW", "on")
    monkeypatch.setattr(law, "_unit", lambda *a: 0.0)  # o roll sempre passa


def _hunted(
    *,
    heat=80,
    bounty=280,
    capital=True,
    shown=("perguntaram_por_voce",),
    loc="nova_arcadia",
    clock=100,
):
    state = with_clock(base_state(loc), clock)
    state["law_state"] = {
        "wanted": {
            "codigo_de_ferro": {
                "jurisdiction_id": "codigo_de_ferro",
                "heat": heat,
                "bounty": bounty,
                "capital": capital,
                "last_crime_clock": 20 if capital else clock,
                "known_at": {"nova_arcadia": 20, "na_anel_dourado": 22},
                "signals_shown": list(shown),
                "hunters_last_clock": -1,
            }
        }
    }
    return state


def _hint(state, loc=None):
    loc = loc or state["world"]["current_location_id"]
    return law.hunter_encounter(state, loc, law.clock_of(state))


def test_hunters_need_cacado_and_prior_signal():
    assert _hint(_hunted())["reason"] == "bounty_hunters"
    assert _hint(_hunted(shown=())) is None  # telegrafado: sem o sinal, sem caçador
    assert _hint(_hunted(heat=40, capital=False)) is None  # `procurado` não basta
    assert _hint(_hunted(clock=22)) is None  # a notícia chegou há < hunter_delay_periods


def test_hunters_respect_spacing_between_waves():
    state = _hunted()
    first = _hint(state)
    upd = law.mark_hunters(state, first["jurisdiction_id"], law.clock_of(state))
    assert _hint({**state, **upd}) is None  # acabou de vir um bando


def test_hunters_respect_global_cooldown():
    world = {
        "current_location_id": "nova_arcadia",
        "current_location": "Nova Arcádia",
        "last_encounter_turn": 9,
        "danger_level": 5,
    }
    hint = _hint(_hunted())
    assert world_utils.check_encounter(world, [], {}, 10, law_hint=hint) is None  # cooldown
    enc = world_utils.check_encounter(dict(world), [], {}, 40, law_hint=hint)
    assert enc["reason"] == "bounty_hunters" and enc["enemy_id"] == hint["enemy_id"]


def test_hunters_priority_after_reinforcements_before_ruler(monkeypatch):
    world = {"current_location_id": "nova_arcadia", "current_location": "Nova Arcádia"}
    hint = _hint(_hunted())
    ruler = {"id": "legiao_ferro", "name": "Legião"}
    monkeypatch.setattr(world_utils, "_hostile_ruler", lambda *a, **k: ruler)
    enc = world_utils.check_encounter(dict(world), [], {}, 40, law_hint=hint)
    assert enc["reason"] == "bounty_hunters"  # antes do domínio de fação
    monkeypatch.setattr(
        world_utils, "_pop_active_alert", lambda *a, **k: {"hint": "fugitivos", "enemy_id": ""}
    )
    enc = world_utils.check_encounter(dict(world), [], {}, 40, law_hint=hint)
    assert enc["reason"] == "reinforcements"  # reforços vêm antes dos caçadores


def test_hunters_radius_world_distance():
    near = _hint(_hunted(), "na_anel_lama")  # colado em Nova Arcádia
    assert near is not None
    assert _hint(_hunted(), "skallgard") is not None  # distância 4 = limite do raio
    assert _hint(_hunted(), "selva_xylos") is None  # distância 5: fora do raio


def test_hunter_strength_ignores_player_level():
    hint = _hint(_hunted())
    effs = []
    for level in (1, 8):
        world = {"current_location_id": "nova_arcadia", "current_location": "Nova Arcádia"}
        enc = world_utils.check_encounter(world, [], {}, 40, player_level=level, law_hint=hint)
        assert enc["reason"] == "bounty_hunters"
        effs.append(world["encounter_eff_danger"])
    assert effs[0] == effs[1] == hint["eff_danger"]
    # a força sobe com o preço pela cabeça
    cheap = _hint(_hunted(bounty=60, capital=False, heat=70))
    rich = _hint(_hunted(bounty=400))
    assert cheap["eff_danger"] < rich["eff_danger"]
    assert cheap["enemy_id"] == "enemy_bandido" and rich["enemy_id"] == "enemy_bandido_capitao"


def test_check_encounter_identical_without_law_hint():
    def world():
        return {
            "current_location_id": "pantano_melancolia",
            "current_location": "Pântano",
            "danger_level": 5,
        }

    a = world_utils.check_encounter(world(), [], {}, 40)
    b = world_utils.check_encounter(world(), [], {}, 40, law_hint=None)
    assert a == b


def test_hunter_origin_maps_to_law_enforcement():
    assert normalize("law_enforcement") == "law_enforcement"
    assert from_encounter({"reason": "bounty_hunters"}, {}) == "law_enforcement"
    assert from_encounter({"reason": "controlled"}, {}) == "regional_danger"  # inalterado


def test_hunters_off_in_shadow_and_off(monkeypatch):
    for mode in ("off", "shadow"):
        monkeypatch.setenv("RPG_LAW", mode)
        assert _hint(_hunted()) is None


def test_storyteller_travel_spawns_hunters_after_signal(monkeypatch):
    """Integração: viajar com caçador no radar vira combate `law_enforcement` e marca o bando."""
    from langchain_core.messages import HumanMessage

    from agents import storyteller

    monkeypatch.setattr(law, "patrol_present", lambda *a, **k: False)
    state = _hunted(clock=100)
    state["messages"] = [HumanMessage(content="vou para o Pântano da Melancolia")]
    state["world"] = {**state["world"], "last_encounter_turn": -99}
    out = storyteller.storyteller_node(state)
    assert out["next"] == "combat_agent"
    assert out["combat_origin_hint"] == "law_enforcement"
    assert out["combat_encounter_hint"]["reason"] == "bounty_hunters"
    assert out["law_state"]["wanted"]["codigo_de_ferro"]["hunters_last_clock"] >= 0
    # sem o sinal prévio o mesmo trajeto NÃO traz caçadores
    quiet = _hunted(clock=100, shown=())
    quiet["messages"] = state["messages"]
    quiet["world"] = dict(state["world"])
    assert storyteller.storyteller_node(quiet).get("combat_origin_hint") != "law_enforcement"
