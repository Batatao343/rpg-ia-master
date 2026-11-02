"""SPEC-351 Etapa 4 — estado (opening_thread, fichas) e planejador (R10–R13)."""

from __future__ import annotations

import agents.campaign_manager as cm
from services import opening_threads as ot
from services import prologue

CHAR = {
    "name": "Aranel",
    "race": "Elfo",
    "class_name": "Arcanista Cinzento",
    "region": "Nova Arcádia",
    "level": 1,
    "backstory": "saí do Anel Dourado depois que minha irmã parou de me reconhecer",
}


def _seeded(start="nova_arcadia"):
    scenario, _m, ctx = prologue.build_start_scenario_ctx(CHAR)
    menu = ctx["menu"]
    seed = prologue.scenario_to_state_seed(
        scenario, {**CHAR, "game_id": "g-351"}, start, menu=menu, pool_seed=ctx["seed"]
    )
    return scenario, menu, seed


def test_seed_writes_opening_thread():
    scenario, menu, seed = _seeded()
    thread = seed["campaign_plan"]["opening_thread"]
    assert thread["thread_refs"] == scenario.thread_refs
    assert thread["arcs_left"] == 2 and thread["region_id"] == "nova_arcadia"
    assert thread["seeking"] == scenario.seeking
    assert thread["plot_npc_key"] in seed["npcs"] and thread["personal_npc_key"] in seed["npcs"]


def test_old_save_without_thread_loads():
    plan = {"location": "Nova Arcádia", "beats": [], "climax": "", "current_step": 0}
    assert ot.planner_thread_block({"campaign_plan": plan, "world": {}}) == ""
    assert ot.active_thread({"campaign_plan": plan}) is None


def test_plot_npc_sheet_uses_graph_id_and_stub():
    scenario, menu, seed = _seeded()
    row = next(n for n in menu["npcs"] if n["entity_id"] == scenario.plot_npc_id)
    sheet = seed["npcs"][row["name"]]
    assert sheet["id"] == row["entity_id"]
    assert sheet["sheet_status"] == "stub" and sheet["relationship"] == 5
    assert sheet["known_by_player"] is True


def test_plot_npc_in_scene_only_at_home():
    scenario, menu, _seed = _seeded()
    row = next(n for n in menu["npcs"] if n["entity_id"] == scenario.plot_npc_id)
    at_home = ot.plot_npc_sheet(row, "g", row["home_location_id"])
    away = ot.plot_npc_sheet(row, "g", "outro_lugar")
    assert at_home["in_scene"] is True and away["in_scene"] is False
    seed = prologue.scenario_to_state_seed(
        scenario, {**CHAR, "game_id": "g"}, "outro_lugar", menu=menu
    )
    assert "outro lugar da região" in seed["opening_message"]


def test_personal_npc_local_has_bond_and_seed_motives():
    scenario, _menu, seed = _seeded()
    sheet = seed["npcs"][scenario.personal_npc.name]
    assert sheet["bond"] == scenario.personal_npc.bond
    assert set(sheet["seed_motives"]) == {
        "desire_id",
        "fear_id",
        "secret_id",
        "contradiction_id",
        "mannerism_id",
    }
    assert sheet["in_scene"] is True and sheet["relationship"] in (2, 5, 8)


def _state(seed, loc="nova_arcadia"):
    return {
        "campaign_plan": seed["campaign_plan"],
        "npcs": seed["npcs"],
        "world": {"current_location": "Nova Arcádia", "current_location_id": loc, "turn_count": 20},
        "messages": [],
    }


def test_planner_receives_thread_block_and_decrements(monkeypatch):
    _s, _m, seed = _seeded()
    state = _state(seed)
    seen = {"invokes": 0, "system": ""}

    class _LLM:
        def with_structured_output(self, _m):
            return self

        def invoke(self, msgs):
            seen["invokes"] += 1
            seen["system"] = msgs[0].content
            return cm.CampaignPlanModel(
                location="Nova Arcádia",
                beats=["Descreva a viela.", "Mostre o frasco.", "Siga o rastro."],
                climax="Um acerto de contas.",
                arc_title="Rastro do Pó",
            )

    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: _LLM())
    plan = cm._build_plan(state)
    assert seen["invokes"] == 1  # sem LLM nova
    assert "<FIO_DE_ABERTURA>" in seen["system"] and "O herói busca" in seen["system"]
    assert plan["opening_thread"]["arcs_left"] == 1
    # 2º replanejamento consome o último arco; o 3º já não leva o bloco
    state["campaign_plan"] = plan
    plan2 = cm._build_plan(state)
    assert plan2["opening_thread"]["arcs_left"] == 0
    state["campaign_plan"] = plan2
    assert ot.planner_thread_block(state) == ""
    plan3 = cm._build_plan(state)
    assert "opening_thread" not in plan3
    assert "<FIO_DE_ABERTURA>" not in seen["system"]


def test_planner_block_absent_after_arcs_or_region_change():
    _s, _m, seed = _seeded()
    assert ot.planner_thread_block(_state(seed)).startswith("<FIO_DE_ABERTURA>")
    assert ot.planner_thread_block(_state(seed, loc="skallgard")) == ""  # saiu da região
    seed["campaign_plan"]["opening_thread"]["arcs_left"] = 0
    assert ot.planner_thread_block(_state(seed)) == ""


def test_planner_lore_query_includes_door_names(monkeypatch):
    _s, _m, seed = _seeded()
    state = _state(seed)
    names = ot.door_names(state["campaign_plan"]["opening_thread"])
    assert names
    captured = {}
    import services.lore_query as lq

    real = lq.compose_lore_query
    monkeypatch.setattr(lq, "compose_lore_query", lambda s, i: real(s, i))
    orig_pack = cm.build_context_pack

    def spy(st, *, query, purpose):
        captured["q"] = query
        return orig_pack(st, query=query, purpose=purpose)

    monkeypatch.setattr(cm, "build_context_pack", spy)
    cm._build_plan(state)
    assert names[0] in captured["q"]


def test_seeded_plan_survives_first_invoke():
    _s, _m, seed = _seeded()
    state = _state(seed)
    state["campaign_plan"]["last_planned_turn"] = state["world"]["turn_count"]
    state["campaign_plan"]["location"] = "Nova Arcádia"
    assert cm._should_replan(state) is False
