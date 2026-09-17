from __future__ import annotations

import asyncio
import threading
import time

from langchain_core.messages import AIMessage, HumanMessage

import llm_setup
from llm_setup import ModelTier, RoutedLLM
from services.turn_pipeline import StageInterval, summarize_stage_intervals


def test_langgraph_plan_and_route_overlap_with_disjoint_updates(monkeypatch):
    import main

    barrier = threading.Barrier(2, timeout=2)
    intervals: dict[str, tuple[float, float]] = {}

    def branch(name, update):
        def run(_state):
            started = time.perf_counter()
            barrier.wait()
            time.sleep(0.05)
            intervals[name] = (started, time.perf_counter())
            return update
        return run

    monkeypatch.setenv("RPG_TURN_EXECUTION", "concurrent")
    monkeypatch.setattr(main, "campaign_manager_node", branch("plan", {
        "campaign_plan": {"location": "Nova Arcádia", "beats": []},
        "needs_replan": False,
    }))
    monkeypatch.setattr(main, "route_intent_node", branch("route", {
        "next": "storyteller",
    }))
    monkeypatch.setattr(main, "storyteller_node", lambda _state: {
        "messages": [AIMessage(content="Cena pronta.")],
    })
    monkeypatch.setattr(main, "archive_node", lambda _state: {})
    monkeypatch.setattr(main, "turn_finalizer_node", lambda _state: {})
    graph = main.build_game_graph()
    state = {
        "game_id": "concurrent-turn",
        "player": {"conscious": True, "gold": 0, "xp": 0, "level": 1,
                   "inventory": []},
        "world": {"turn_count": 0, "current_location": "Nova Arcádia",
                  "current_location_id": "nova_arcadia"},
        "continuity": {}, "combat": {"active": False},
        "messages": [HumanMessage(content="Observo a praça")],
        "quests": [], "event_log": [],
    }

    final = graph.invoke(state)

    assert final["world"]["turn_count"] == 1
    assert final["turn_prepared"] is False
    assert intervals["plan"][0] < intervals["route"][1]
    assert intervals["route"][0] < intervals["plan"][1]


def test_routed_llm_ainvoke_preserva_fallback_sem_bloquear_event_loop(monkeypatch):
    class Client:
        def __init__(self, fail=False):
            self.fail = fail

        def invoke(self, _input):
            time.sleep(0.04)
            if self.fail:
                raise RuntimeError("falha")
            return AIMessage(content="ok")

    llm_setup._CLIENT_CACHE.clear()
    monkeypatch.setattr(
        llm_setup,
        "_get_cached_client",
        lambda provider, _model, _temperature: Client(fail=provider == "a"),
    )
    routed = RoutedLLM(ModelTier.FAST, 0.0, [("a", "m1"), ("b", "m2")])

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0.01)
                ticks += 1

        result, _ = await asyncio.gather(routed.ainvoke("x"), ticker())
        return result, ticks

    result, ticks = asyncio.run(scenario())
    assert result.content == "ok"
    assert ticks == 5


def test_world_pulse_proposal_is_pure_and_apply_is_single_commit(monkeypatch):
    from agents import world_simulator as ws

    class Structured:
        def with_structured_output(self, _schema):
            return self

        def invoke(self, _messages):
            return ws.WorldPulse(rumor="Sinos ecoam ao longe.", danger_shift=1)

    monkeypatch.setattr(ws, "get_llm", lambda **_kwargs: Structured())
    world = {
        "current_location_id": "nova_arcadia",
        "current_location": "Nova Arcádia",
        "danger_level": 1,
    }
    original = dict(world)

    proposal = ws.propose_world_pulse({}, world, [], {}, 1)
    assert world == original
    applied, note, intents = ws.apply_world_pulse(world, proposal)
    assert world == original
    assert applied["danger_level"] == 2
    assert note == "[ECOS DO MUNDO] Sinos ecoam ao longe."
    assert len(intents) == 1


def test_stage_metrics_distinguish_critical_path_work_and_overlap():
    summary = summarize_stage_intervals([
        StageInterval("plan", 0, 80),
        StageInterval("route", 10, 60),
        StageInterval("dispatch", 80, 90),
    ])
    assert summary == {
        "critical_path_ms": 90,
        "work_ms": 140,
        "overlap_ms": 50,
    }


def test_sequential_and_concurrent_graphs_have_same_canonical_result(monkeypatch):
    import copy
    import main

    calls = {"plan": 0, "route": 0}

    def plan(_state):
        calls["plan"] += 1
        return {
            "campaign_plan": {"location": "Brekmar", "beats": []},
            "needs_replan": False,
        }

    def route(_state):
        calls["route"] += 1
        return {"next": "storyteller"}

    monkeypatch.setattr(main, "campaign_manager_node", plan)
    monkeypatch.setattr(main, "route_intent_node", route)
    monkeypatch.setattr(main, "storyteller_node", lambda _state: {
        "messages": [AIMessage(content="Resultado estável.")],
    })
    monkeypatch.setattr(main, "archive_node", lambda _state: {})
    monkeypatch.setattr(main, "turn_finalizer_node", lambda _state: {})
    state = {
        "game_id": "equivalence", "player": {"conscious": True},
        "world": {"turn_count": 0, "current_location_id": "brekmar",
                  "current_location": "Brekmar"},
        "continuity": {}, "combat": {"active": False},
        "messages": [HumanMessage(content="Observo")],
        "quests": [], "event_log": [],
    }

    monkeypatch.setenv("RPG_TURN_EXECUTION", "sequential")
    serial = main.build_game_graph().invoke(copy.deepcopy(state))
    monkeypatch.setenv("RPG_TURN_EXECUTION", "concurrent")
    parallel = main.build_game_graph().invoke(copy.deepcopy(state))

    assert parallel == serial
    assert calls == {"plan": 2, "route": 2}


def test_provider_limit_one_serializes_parallel_ainvoke(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    class Client:
        def invoke(self, _input):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return AIMessage(content="ok")

    monkeypatch.setenv("RPG_LLM_MAX_CONCURRENCY_FAKE", "1")
    monkeypatch.setattr(llm_setup, "_get_cached_client", lambda *_args: Client())
    routed = RoutedLLM(ModelTier.FAST, 0.0, [("fake", "m")])

    async def scenario():
        return await asyncio.gather(routed.ainvoke("a"), routed.ainvoke("b"))

    results = asyncio.run(scenario())
    assert [result.content for result in results] == ["ok", "ok"]
    assert peak == 1


def test_plan_refresh_is_deferred_during_active_combat(monkeypatch):
    from agents import campaign_manager

    monkeypatch.setattr(
        campaign_manager, "_build_plan",
        lambda _state: (_ for _ in ()).throw(AssertionError("SMART não deve rodar")),
    )
    state = {
        "game_id": "combat-replan",
        "world": {"turn_count": 12, "current_location": "Brekmar"},
        "continuity": {}, "turn_prepared": True,
        "combat": {"active": True}, "needs_replan": True,
        "campaign_plan": {"location": "Brekmar", "beats": []},
    }

    update = campaign_manager.campaign_manager_node(state)

    assert update["needs_replan"] is True
    assert update["campaign_plan"] == state["campaign_plan"]
