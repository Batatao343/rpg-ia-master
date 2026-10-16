"""SPEC-233 — perigo efetivo, controle dinâmico, luz, clima/reforços, storyteller, laboratório."""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import api
import world_utils as wu
from services import graph_resolver as gr


def _player(**over):
    p = {"name": "Kael", "class_name": "Guerreiro", "level": 1, "inventory": [], "equipment": {}}
    p.update(over)
    return p


def test_travel_uses_effective_danger():  # R1
    from gamedata import get_location
    dest = get_location("na_anel_dourado")
    world = wu.ensure_world({"current_location_id": "nova_arcadia",
                             "danger_overrides": {"na_anel_dourado": 4}})
    out = wu.apply_travel(world, dest)
    assert out["danger_level"] == 4
    assert wu.effective_danger(out) == 4
    assert wu.recovery_rest_safe(1, out["danger_level"], dest) is False


def test_danger_shift_clamp_and_decay():  # R2
    from agents import world_simulator as ws
    w = {"current_location_id": "na_taverna_javali", "turn_count": 1}  # base 0
    out = ws._apply_danger_shift(dict(w), "na_taverna_javali", -1)
    assert ws._effective_danger(out, "na_taverna_javali") == 0
    # cidade (base 1): shifts positivos são ignorados
    w = {"current_location_id": "nova_arcadia", "turn_count": 1}
    for _ in range(3):
        w = ws._apply_danger_shift(w, "nova_arcadia", 1)
    assert ws._effective_danger(w, "nova_arcadia") <= 2
    # drift limitado a base+1 em local comum
    w = {"current_location_id": "pm_profundezas", "turn_count": 1}
    from gamedata import get_location
    base = get_location("pm_profundezas")["danger"]
    for _ in range(4):
        w = ws._apply_danger_shift(w, "pm_profundezas", 1)
    assert ws._effective_danger(w, "pm_profundezas") <= min(4, base + 1)
    # decaimento de 1 a cada 10 turnos sem shift
    w["turn_count"] = 25
    w = wu.decay_danger_overrides(w)
    assert ws._effective_danger(w, "pm_profundezas") == base


def test_dungeon_is_dark_without_torch():  # R3
    w = {"current_location_id": "pm_cripta_afogada", "time_of_day": "Manhã"}
    assert wu.light_level(w, _player())["dark"] is True
    lit = wu.light_level(w, _player(inventory=[{"id": "tocha_resina", "qty": 1}]))
    assert lit["dark"] is False and lit["lit"] is True


def test_disabled_dynamic_edge():  # R4
    proj = {"dynamic_edges": [{"id": "dyn_abc", "source": "mao_sombria",
                               "type": "controls", "target": "nova_arcadia"}],
            "disabled_edges": [{"edge_id": "dyn_abc"}]}
    gr.clear_cache()
    assert gr.get_current_controller("nova_arcadia", proj) != "mao_sombria"


def test_eff_danger_flag_one_shot():  # R5
    world = {"current_location_id": "nova_arcadia", "last_encounter_turn": -99,
             "current_location": "Nova Arcádia"}
    assert wu.check_encounter(world, [], {}, turn=10, player_level=1) is None
    assert "encounter_eff_danger" not in world


def test_reinforcement_alert_not_deduped():  # R6
    import agents.storyteller as stt
    world = wu.register_flee_alert(
        {"current_location_id": "pm_profundezas", "last_encounter_turn": -99,
         "last_encounter_id": "Lobo", "last_encounter_loc": "pm_profundezas"},
        "Lobo", turn=5)
    enc = wu.check_encounter(world, [], {}, turn=6, player_level=5)
    assert enc and enc["reason"] == "reinforcements"
    assert stt._dedupe_encounter(enc, {**world, "current_location_id": "pm_profundezas",
                                       "last_encounter_id": enc["hint"],
                                       "last_encounter_loc": "pm_profundezas"}) is enc
    assert not world["threat_alerts"]


def test_weather_duration_by_steps():  # R7
    w = {"current_location_id": "nova_arcadia", "danger_level": 1,
         "weather_global": {"id": "tempestade_de_eter", "periods_left": 4}}

    class R:
        def random(self): return 0.99
        def choices(self, p, weights=None, k=1): return [p[0]]
        def choice(self, s): return s[0]
    wu.advance_weather(w, R(), steps=3)
    assert w["weather_global"]["periods_left"] == 1


def test_storyteller_exception_keeps_rest(monkeypatch):  # R8
    import agents.storyteller as stt
    from langchain_core.messages import HumanMessage

    class _Boom:
        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, *_a, **_k):
            raise RuntimeError("provider caiu")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Boom())
    state = {"game_id": "pytest233", "narrative_summary": "", "archivist_last_run": 0,
             "messages": [HumanMessage(content="Descanso até recuperar as forças")],
             "npcs": {}, "factions": [], "faction_intel": {}, "campaign_plan": {},
             "player": {"name": "T", "class_name": "Guerreiro", "level": 1,
                        "vitalidade": 2, "max_vitalidade": 20},
             "world": {"current_location": "Nova Arcádia", "current_location_id": "nova_arcadia",
                       "turn_count": 5, "time_of_day": "Dia", "danger_level": 1,
                       "world_clock": {"day": 1, "period": "Manhã"}, "quest_plan": []}}
    out = stt.storyteller_node(state)
    assert out["player"]["vitalidade"] > 2
    assert out["world"]["world_clock"] != {"day": 1, "period": "Manhã"}
    text = out["messages"][-1].content
    assert "O jogador" not in text and "DESCANSOU" not in text


def test_finished_simulation_rejects_action(monkeypatch):  # R9
    saved = {}

    def save(state):
        saved[state["game_id"]] = deepcopy(state)
        return True

    def load(path=None):
        if not path:
            return None
        gid = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(saved.get(gid))
    monkeypatch.setattr(api, "save_game_state", save)
    monkeypatch.setattr(api, "load_game_state", load)
    client = TestClient(api.app)
    created = client.post("/game/combat-simulator", json={
        "class_name": "Sangromante", "level": 3, "enemy_id": "mon_cao_rebite", "quantity": 1}).json()
    st = saved[created["game_id"]]
    st["combat"]["active"] = False
    saved[created["game_id"]] = st
    r = client.post("/game/action", json={"game_id": created["game_id"],
                                          "input_text": "Viajo para Brekmar"})
    assert r.status_code == 409
    assert "simulation_finished" in r.text
    assert saved[created["game_id"]].get("archivist_last_run", 0) == 0


def test_ascension_override_survives_drift_and_decay():  # R2 (revisão Sol)
    from agents import world_simulator as ws
    from gamedata import get_location
    base = get_location("pm_profundezas")["danger"]
    # drift carimbado, depois ascensão de facção sobe o perigo do mesmo local
    w = {"current_location_id": "pm_profundezas", "turn_count": 1}
    w = ws._apply_danger_shift(w, "pm_profundezas", -1)
    wu._raise_danger(w, "pm_profundezas")
    raised = wu._effective_danger(w, "pm_profundezas")
    assert "pm_profundezas" not in (w.get("danger_shift_turns") or {})
    # pulso negativo não corrói a ascensão e o decaimento não a devolve ao base
    w = ws._apply_danger_shift(w, "pm_profundezas", -1)
    w["turn_count"] = 99
    w = wu.decay_danger_overrides(w)
    assert wu._effective_danger(w, "pm_profundezas") == raised
    assert raised == min(4, base)  # base-1 + 1


def test_world_simulator_reads_dict_override():  # R1 compat
    from agents import world_simulator as ws
    w = {"danger_overrides": {"nova_arcadia": {"value": 3}}}
    assert ws._effective_danger(w, "nova_arcadia") == 3


def test_ensure_world_corrects_stale_danger_from_old_save():
    import world_utils
    w = world_utils.ensure_world({})
    expected = w["danger_level"]
    stale = {**w, "danger_level": 9}
    assert world_utils.ensure_world(stale)["danger_level"] == expected
