"""SPEC-199 - XP e recibo numerico fora da prosa; turn_outcome estruturado."""
from __future__ import annotations

import json
import re

from langchain_core.messages import AIMessage, HumanMessage

from services import turn_outcome as to
from tests.test_bug_contabilidade_recompensas import _combat_state


def _kill_state(monkeypatch, narrate=None):
    from agents import combat as cbt
    from services import conflict_orchestrator as orch
    captured = {}

    def fake_narrate(player, enemies, logs, *a, **k):
        captured["logs"] = list(logs)
        return "Fim."

    monkeypatch.setattr(cbt, "_narrate", narrate or fake_narrate)

    def fake_run_round(scene, actors_by_id, sides, *a, **k):
        victim = actors_by_id.get("enemy_rato_peste_anel_lama_1")
        victim.update({"hp": 0, "vitalidade": 0, "dead": True, "status": "morto"})
        return {"logs": ["Voce acerta o rato."], "deaths": [], "terminal": [], "abyss": [],
                "attacks": [], "reactions": [], "last_stands": [], "stabilizations": [],
                "scars_pending": [], "resolved_turns": ["player"], "cards_used": [],
                "recidiva_event": None, "reason": None, "ended": False, "player_dead": False}

    monkeypatch.setattr(orch, "run_round", fake_run_round)
    state = _combat_state()
    victim = {**state["enemies"][1], "id": "enemy_rato_peste_anel_lama_1"}
    other = {**state["enemies"][1], "id": "e3", "name": "Goblin C"}
    state["enemies"] = [victim, other]
    state["player"]["xp"] = 0
    state["turn_baseline"] = {"gold": 0, "xp": 0, "level": 1}
    return cbt, state, captured


def test_combat_logs_have_no_reward_lines(monkeypatch):
    cbt, state, cap = _kill_state(monkeypatch)
    out = cbt.combat_node(state)
    assert out["player"]["xp"] == 50  # R2: grant unico, regra inalterada
    assert cap["logs"]
    assert not any(re.search(r"XP|N[IÍ]VEL", l) for l in cap["logs"])


def test_fall_and_fallback_prose_have_no_reward_numbers(monkeypatch):
    cbt, state, cap = _kill_state(monkeypatch, narrate=None)
    # forca o fallback real de _narrate (LLM indisponivel)
    monkeypatch.undo()
    from agents import combat as cbt2
    from services import conflict_orchestrator as orch

    class Boom:
        def invoke(self, *a, **k):
            raise RuntimeError("down")

    monkeypatch.setattr(cbt2, "get_llm", lambda *a, **k: Boom(), raising=False)
    text = cbt2._narrate({"name": "A"}, [], ["Voce acerta o rato."], None, "x", True, "")
    assert "XP" not in text and "NÍVEL" not in text
    assert "XP" not in cbt2._narrate_fall({"name": "A"}, ["Voce acerta."], "Rato")


def test_render_player_message_has_no_receipt():
    out = {"xp_delta": 50, "gold_delta": 10, "items_gained": {"x": 1}, "quests_completed": ["q"]}
    text = to.render_player_message("O rato tomba.", out)
    assert text == "O rato tomba."


def test_negative_reward_phrase_still_stripped_when_gain():
    text = to.render_player_message("Voce vence. Nada novo foi obtido.", {"xp_delta": 50})
    assert "Nada novo" not in text and "Voce vence" in text


def test_public_outcome_whitelist_and_names():
    raw = {"receipt_id": "r1", "turn": 3, "xp_delta": 50, "level_delta": 1, "level_after": 2,
           "gold_delta": 5, "items_gained": {"pocao_cura_menor": 2},
           "quests_completed": ["q1"], "event_ids": ["e1"], "transition_readiness": {"a": 1},
           "source": "combat"}
    pub = to.public_outcome(raw)
    assert "event_ids" not in pub and "transition_readiness" not in pub
    assert pub["items_gained"][0]["qty"] == 2 and pub["items_gained"][0]["name"]
    assert pub["quests_completed"] == [{"id": "q1", "title": "q1"}]
    assert pub["source"] == "combat"
    assert to.public_outcome({}) == {} and to.public_outcome(None) == {}


def test_strip_receipt_legacy_message():
    assert to.strip_receipt("Fim.\n\n[RESULTADO] +50 XP") == "Fim."
    state = {"messages": [], "last_turn_outcome": {"player_message": "Fim.\n\n[RESULTADO] +50 XP"}}
    assert to.player_facing_message(state) == "Fim."


def test_finalize_outcome_message_without_numbers_and_source():
    state = {"game_id": "g", "world": {"turn_count": 4},
             "player": {"xp": 50, "gold": 0, "level": 2, "inventory": []},
             "turn_baseline": {"turn": 4, "xp": 0, "gold": 0, "level": 1, "inventory": {}},
             "messages": [AIMessage(content="O rato tomba.")]}
    out = to.finalize_outcome(state)
    assert out["xp_delta"] == 50 and out["level_after"] == 2 and out["source"] == "combat"
    assert "XP" not in out["player_message"] and "[RESULTADO]" not in out["player_message"]


def _fmt_state(**over):
    from tests.test_fase43 import make_player
    s = {"game_id": "g", "player": make_player(hp=10, inventory=[]), "world": {"current_location": "Nova Arcadia", "current_location_id": "nova_arcadia"}, "messages":
         [HumanMessage(content="a"), AIMessage(content="Fim.")], "enemies": [], "npcs": {}}
    s.update(over)
    return s


def test_response_turn_outcome_empty_for_legacy_save_and_simulation():
    import api
    assert api.format_response(_fmt_state()).turn_outcome == {}
    lo = {"receipt_id": "r", "turn": 1, "xp_delta": 5, "player_message": "Fim."}
    assert api.format_response(_fmt_state(last_turn_outcome=lo)).turn_outcome["xp_delta"] == 5
    sim = api.format_response(_fmt_state(last_turn_outcome=lo, combat_simulation={"enabled": True}))
    assert sim.turn_outcome == {}


def test_save_reload_keeps_outcome():
    import api
    from persistence import _raw_to_state, _state_to_save_data
    lo = {"receipt_id": "r9", "turn": 2, "xp_delta": 50, "level_delta": 0, "level_after": 1,
          "gold_delta": 0, "items_gained": {}, "quests_completed": [], "player_message": "Fim."}
    state = _fmt_state(last_turn_outcome=lo, continuity={}, party=[])
    before = api.format_response(state).turn_outcome
    raw = json.loads(json.dumps(_state_to_save_data(state, "g")))
    after = api.format_response({**state, **_raw_to_state(raw)}).turn_outcome
    assert before == after and after["receipt_id"] == "r9"
