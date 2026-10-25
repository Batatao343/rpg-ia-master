"""SPEC-318 R6/R7: nó `enrich` entre o narrador e o arquivista, e paridade com o HEAD."""

from __future__ import annotations

import copy
import json
import random

import pytest
from langgraph.graph import END, START, StateGraph

import persistence

LEGACY_FLAGS = {
    "RPG_DAY_DIGEST": "llm",
    "RPG_ARCHIVE_POLICY": "legacy",
    "RPG_NPC_TWO_PHASE": "off",
    "RPG_REPLAN_AFTER": "off",
}


def _initial_state(seed: int) -> dict:
    from playtest.runner import _build_initial_state

    random.seed(seed)
    return _build_initial_state("explorador", seed)


def _head_graph():
    """Topologia do HEAD (antes da SPEC-318): sem `enrich`, replan sempre na frente do router."""
    from agents.action_guard import action_guard_node
    from agents.archivist import archive_node
    from agents.campaign_manager import campaign_manager_node
    from agents.combat import combat_node
    from agents.loot import loot_node
    from agents.npc import npc_actor_node
    from agents.storyteller import storyteller_node
    from agents.turn_finalizer import turn_finalizer_node
    from observability.telemetry import with_node
    from services.turn_pipeline import dispatch_node, route_intent_node, turn_prepare_node
    from state import GameState

    wf = StateGraph(GameState)
    for name, fn in (
        ("campaign_manager", campaign_manager_node),
        ("dm_router", route_intent_node),
        ("storyteller", storyteller_node),
        ("combat_agent", combat_node),
        ("npc_actor", npc_actor_node),
        ("loot_agent", loot_node),
        ("archivist", archive_node),
        ("action_guard", action_guard_node),
        ("turn_finalizer", turn_finalizer_node),
        ("turn_prepare", turn_prepare_node),
        ("dispatch", dispatch_node),
    ):
        wf.add_node(name, with_node(name, fn))
    wf.add_conditional_edges(
        START,
        lambda s: (
            "__end__"
            if (s.get("game_over") or s.get("death_pending") or s.get("archived"))
            else "action_guard"
        ),
        {"__end__": END, "action_guard": "action_guard"},
    )
    wf.add_conditional_edges(
        "action_guard",
        lambda s: "__end__" if s.get("action_guard_blocked") else "turn_prepare",
        {"__end__": END, "turn_prepare": "turn_prepare"},
    )
    wf.add_edge("turn_prepare", "campaign_manager")
    wf.add_edge("campaign_manager", "dm_router")
    wf.add_edge("dm_router", "dispatch")
    wf.add_conditional_edges(
        "dispatch",
        lambda s: s.get("next"),
        {
            "storyteller": "storyteller",
            "combat_agent": "combat_agent",
            "npc_actor": "npc_actor",
            "loot": "loot_agent",
            END: END,
        },
    )
    wf.add_edge("loot_agent", "archivist")
    wf.add_conditional_edges(
        "npc_actor",
        lambda s: "storyteller" if s.get("next") == "storyteller" else "archivist",
        {"storyteller": "storyteller", "archivist": "archivist"},
    )
    wf.add_conditional_edges(
        "storyteller",
        lambda s: "combat_agent" if s.get("next") == "combat_agent" else "archivist",
        {"combat_agent": "combat_agent", "archivist": "archivist"},
    )
    wf.add_conditional_edges(
        "combat_agent",
        lambda s: (
            "__end__"
            if (s.get("combat_simulation") or {}).get("enabled")
            else "loot_agent"
            if s.get("next") == "loot"
            else "archivist"
        ),
        {"loot_agent": "loot_agent", "archivist": "archivist", "__end__": END},
    )
    wf.add_edge("archivist", "turn_finalizer")
    wf.add_edge("turn_finalizer", END)
    return wf.compile()


def _plain(state: dict) -> str:
    return json.dumps(
        state,
        default=lambda o: {
            "type": getattr(o, "type", type(o).__name__),
            "c": getattr(o, "content", str(o)),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def test_graph_has_enrich_between_narrator_and_archivist(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    from main import app

    nodes = []
    for mode, data in app.stream(_initial_state(3), stream_mode=["updates"]):
        nodes.extend(data.keys()) if mode == "updates" else None
    assert "enrich" in nodes
    narr = next(i for i, n in enumerate(nodes) if n in ("storyteller", "npc_actor", "loot_agent"))
    assert narr < nodes.index("enrich") < nodes.index("archivist") < nodes.index("turn_finalizer")


def test_enrich_failure_does_not_break_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    import agents.enrich as enrich
    from main import app

    def boom(_state):
        raise RuntimeError("enrich quebrou")

    monkeypatch.setattr(enrich, "_enrich_npcs", boom)
    monkeypatch.setattr(enrich, "_enrich_plan", boom)
    out = app.invoke(_initial_state(4))
    assert out["messages"][-1].content  # a narracao saiu e o turno terminou
    assert out["world"]["turn_count"] >= 1


def test_enrich_is_noop_in_combat_simulation():
    from agents.enrich import enrich_node

    assert (
        enrich_node(
            {"combat_simulation": {"enabled": True}, "npcs": {"x": {"sheet_status": "stub"}}}
        )
        == {}
    )


def test_enrich_never_touches_messages():
    from agents.enrich import enrich_node

    out = enrich_node({"npcs": {}, "world": {"turn_count": 2}, "campaign_plan": {"beats": [1]}})
    assert "messages" not in out


@pytest.mark.parametrize(
    "texts",
    [
        ["olho ao redor", "sigo em frente", "descanso um pouco"],
        ["procuro tesouro no local", "vasculho os arredores", "olho ao redor"],
        ["converso com o estalajadeiro", "pergunto sobre rumores", "olho ao redor"],
    ],
)
def test_legacy_flags_byte_identical(tmp_path, monkeypatch, texts):
    """R7: com as 4 flags no valor legado, o estado final == topologia do HEAD."""
    from langchain_core.messages import HumanMessage

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    for key, value in LEGACY_FLAGS.items():
        monkeypatch.setenv(key, value)
    from main import app

    # O LangGraph sorteia o id de checkpoint de cada passo no `random` global; um no a mais
    # (o `enrich`) deslocaria o resto da sequencia. Isola esse consumo para comparar o jogo.
    monkeypatch.setattr(random, "getrandbits", random.Random(0).getrandbits)
    import types

    from agents import loot as loot_mod

    # o loot sorteia com `random.Random()` sem semente: fixa para as duas topologias
    monkeypatch.setattr(
        loot_mod, "random", types.SimpleNamespace(Random=lambda *_a: random.Random(5))
    )
    head = _head_graph()
    base = _initial_state(11)

    def run(graph, label):
        # cache de NPC/bestiario de runtime isolado por execucao (senao a 2a corrida acha cache-hit)
        monkeypatch.setenv("RPG_RUNTIME_CACHE_DIR", str(tmp_path / f"runtime-{label}"))
        from infrastructure.runtime import reset_runtime

        reset_runtime()
        random.seed(99)
        state = copy.deepcopy(base)
        for text in texts:
            state["messages"] = [*state["messages"], HumanMessage(content=text)]
            state = {**state, **graph.invoke(state)}
        return state

    new_state, head_state = run(app, "new"), run(head, "head")
    volatile = {"last_turn_audit", "turn_timings"}
    a = {k: v for k, v in new_state.items() if k not in volatile}
    b = {k: v for k, v in head_state.items() if k not in volatile}
    assert set(a) == set(b)
    for key in sorted(a):
        assert _plain(a[key]) == _plain(b[key]), key
