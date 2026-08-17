"""Regressões dos achados do long run real de 200 turnos (2026-08-16)."""

from types import SimpleNamespace
import random

from langchain_core.messages import HumanMessage

from agents import combat as combat_mod
from agents import router as router_mod
from playtest import invariants
from playtest.metrics import quest_request_conversion_count
from playtest.profiles import PROFILES
from playtest.runner import TurnRecord, _campaign_experience_violations
from playtest.telemetry import build_summary, turn_to_record
from playtest.runner import CampaignResult


def _state(**overrides):
    state = {
        "player": {
            "name": "Valen", "vitalidade": 20, "max_vitalidade": 20,
            "hp": 20, "max_hp": 20, "inventory": [],
        },
        "world": {
            "current_location_id": "a", "current_location": "A",
            "danger_level": 1, "visited": ["a"],
        },
        "combat": {"active": False}, "enemies": [], "npcs": {},
        "messages": [], "quests": [], "campaign_plan": {"beats": []},
    }
    state.update(overrides)
    return state


def test_chase_track_change_counts_as_combat_progress():
    base = _state(
        combat={
            "active": True,
            "scene": {"positions": {}},
            "chase": {"trilha": "pressionado", "perseguidores": ["lobo"]},
        },
        enemies=[{"id": "lobo", "status": "ativo", "vitalidade": 5}],
    )
    changed = {
        **base,
        "combat": {
            **base["combat"],
            "chase": {"trilha": "afastado", "perseguidores": ["lobo"]},
        },
    }

    assert invariants.combat_progress_fingerprint(base) != \
        invariants.combat_progress_fingerprint(changed)


def test_sixth_consecutive_flee_attempt_forces_valid_escape():
    chase = {
        "trilha": "pressionado", "perseguidores": ["lobo"],
        "fugitive_id": "player", "alcancado": False, "escapou": False,
    }

    escaped, capped = combat_mod._enforce_flee_attempt_limit(chase, attempts=6)

    assert escaped is True
    assert capped["trilha"] == "escapou"
    assert capped["escapou"] is True
    assert capped["alcancado"] is False


def test_successful_flee_clears_all_transient_combat_state(monkeypatch):
    monkeypatch.setattr(
        "gamedata.get_location",
        lambda location_id: {"id": location_id, "name": "B"},
    )
    monkeypatch.setattr(
        "world_utils.apply_travel",
        lambda world, dest: {
            **world,
            "current_location_id": dest["id"],
            "current_location": dest["name"],
        },
    )
    result = {
        "combat": {
            "active": False, "round": 9, "idle_turns": 2,
            "chase": {"trilha": "escapou"}, "instance_id": "old",
            "origin": "regional_danger", "scene": {"positions": {}},
        },
        "enemies": [{"id": "lobo"}], "combat_target": "Lobo",
        "next": "loot", "combat_origin_hint": "player_provoked",
    }
    state = _state(npcs={"Mara": {"name": "Mara", "in_scene": True}})

    combat_mod._apply_flee_travel(state, result, "b", state["player"], [])

    assert result["world"]["current_location_id"] == "b"
    assert result["enemies"] == []
    assert result["combat_target"] is None
    assert result["next"] is None
    assert result["combat_origin_hint"] is None
    assert result["combat"] == {
        "active": False, "round": 9, "idle_turns": 0,
        "scene": None, "origin": "unknown", "last_player_action": {},
    }


def test_rest_outside_combat_bypasses_llm_and_routes_story(monkeypatch):
    monkeypatch.setattr(
        router_mod, "get_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("descanso explícito não deve chamar o roteador LLM")
        ),
    )
    state = _state(messages=[HumanMessage(
        content="Descanso: monto acampamento para recuperar as forças."
    )])

    out = router_mod.dm_router_node(state)

    assert out["next"] == "storyteller"
    assert out["combat_origin_hint"] is None


class _CombatRouterLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return router_mod.RouterDecision(
            route=router_mod.RouteType.COMBAT,
            loot_context=None,
            target="Lobo",
            reasoning="ameaça contextual",
            confidence=0.9,
        )


def test_contextual_combat_is_not_labeled_player_provoked(monkeypatch):
    monkeypatch.setattr(
        router_mod, "get_llm", lambda *_args, **_kwargs: _CombatRouterLLM(),
    )
    state = _state(messages=[HumanMessage(
        content="Investigo a ameaça próxima com cautela e observo seus rastros."
    )])

    out = router_mod.dm_router_node(state)

    assert out["next"] == "combat_agent"
    assert out["combat_origin_hint"] == "regional_danger"


def test_explicit_attack_remains_player_provoked(monkeypatch):
    monkeypatch.setattr(
        router_mod, "get_llm", lambda *_args, **_kwargs: _CombatRouterLLM(),
    )
    state = _state(messages=[HumanMessage(content="Ataco o lobo com minha espada.")])

    assert router_mod.dm_router_node(state)["combat_origin_hint"] == "player_provoked"


def test_normal_prioritizes_quest_path_then_two_distinct_investigations(monkeypatch):
    graph = {
        "a": [{"id": "b", "name": "B", "danger": 1}],
        "b": [
            {"id": "a", "name": "A", "danger": 1},
            {"id": "c", "name": "C", "danger": 2},
        ],
        "c": [{"id": "b", "name": "B", "danger": 1}],
    }
    monkeypatch.setattr(
        "playtest.profiles._connections", lambda location_id: graph[location_id],
    )
    profile = PROFILES["normal"]
    profile.reset()
    quest = {
        "id": "q1", "title": "O sino perdido", "status": "active",
        "location_id": "c", "created_turn": 1,
        "progress_log": [{"kind": "created", "turn": 1, "detail": ""}],
    }
    state = _state(quests=[quest])

    first = profile.decide(state, random.Random(1)).text
    state["world"] = {**state["world"], "current_location_id": "c", "current_location": "C"}
    quest["progress_log"].append(
        {"kind": "location_reached", "turn": 2, "detail": "c"}
    )
    second = profile.decide(state, random.Random(1)).text
    quest["progress_log"].append({
        "kind": "investigation", "turn": 3, "detail": second,
        "fingerprint": second.casefold(),
    })
    third = profile.decide(state, random.Random(1)).text

    assert "B" in first
    assert "sino perdido" in second.casefold()
    assert second.casefold() != third.casefold()
    assert "sino perdido" in third.casefold()


def test_normal_flees_from_round_three_and_sets_twenty_action_cooldown():
    profile = PROFILES["normal"]
    profile.reset()
    combat = _state(
        combat={"active": True, "round": 3},
        enemies=[{"id": "lobo", "name": "Lobo", "status": "ativo"}],
    )

    assert profile.decide(combat, random.Random(2)).mode == "flee"
    assert profile._combat_cooldown == 20


def test_normal_cooldown_text_has_no_mock_combat_trigger():
    profile = PROFILES["normal"]
    profile.reset()
    profile._step = 4
    profile._combat_cooldown = 5

    action = profile.decide(_state(), random.Random(2)).text.casefold()

    assert not any(
        trigger in action
        for trigger in ("atac", "golpe", "luto", "luta", "espada", "enfrent")
    )


def test_normal_seeks_safer_adjacent_before_routine_rest(monkeypatch):
    monkeypatch.setattr(
        "playtest.profiles._connections",
        lambda _location_id: [
            {"id": "safe", "name": "Refúgio", "danger": 1},
            {"id": "worse", "name": "Covil", "danger": 5},
        ],
    )
    profile = PROFILES["normal"]
    profile.reset()
    profile._step = 7
    state = _state(world={
        "current_location_id": "a", "current_location": "A",
        "danger_level": 4, "visited": ["a"],
    })

    action = profile.decide(state, random.Random(1)).text

    assert "Refúgio" in action
    assert "descans" in action.casefold()


def _quest_records():
    records = []
    for turn in range(1, 6):
        record = TurnRecord(
            turn=turn,
            action="Peço uma tarefa concreta" if turn == 1 else "Exploro",
            route="npc_actor" if turn == 1 else "storyteller",
            latency_ms=1,
        )
        record.quest_requested = turn == 1
        record.quests_before = 0 if turn <= 2 else 1
        record.quests_after = 1 if turn >= 2 else 0
        records.append(record)
    return records


def test_quest_conversion_counts_creation_on_next_turn_once():
    records = _quest_records()

    assert quest_request_conversion_count(records, window=3) == 1


def test_quest_conversion_oracle_and_summary_share_windowed_metric():
    records = _quest_records()
    result = CampaignResult(
        profile="normal", seed=1, turns_completed=5, errors=[], history=records,
        final_state=_state(quests=[{"id": "q1", "status": "active"}]),
        save_path="save.json",
    )

    summary = build_summary(result, [turn_to_record(record) for record in records])
    violations = _campaign_experience_violations(
        "normal", records, result.final_state,
    )

    assert summary["experience_balance"]["quest_request_conversions"] == 1
    assert not any(
        item["check_id"] == "profile.quest_conversion_empty"
        for item in violations
    )
