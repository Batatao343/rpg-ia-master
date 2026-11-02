"""SPEC-351 Etapa 3 — prompt, schema e saneamento do prólogo ligado às tramas."""

from __future__ import annotations

from llm_setup import FallbackLLM
from playtest import opening_checks as oc
from services import opening_threads as ot
from services import prologue
from services.prologue import PersonalNPC, StartScenario

CHAR = {
    "name": "Aranel",
    "race": "Elfo",
    "class_name": "Arcanista Cinzento",
    "region": "Nova Arcádia",
    "level": 1,
    "backstory": "saí do Anel Dourado depois que minha irmã parou de me reconhecer",
}


class _Capture:
    is_mock = False

    def __init__(self, result=None):
        self.result, self.messages = result, []

    def with_structured_output(self, _schema):
        outer = self

        class _B:
            def invoke(self, messages):
                outer.messages = list(messages)
                return outer.result

        return _B()


def _menu():
    return ot.thread_menu(
        "nova_arcadia", backstory=CHAR["backstory"], start_location_id="nova_arcadia"
    )


def test_prompt_has_doors_npcs_lore_and_no_old_rules(monkeypatch):
    llm = _Capture()
    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: llm)
    prologue.build_start_scenario_ctx(CHAR)
    system = llm.messages[0].content
    for tag in (
        "<PORTAS_DE_TRAMA>",
        "<NPCS_DA_TRAMA>",
        "<LORE_DA_REGIAO>",
        "<SEMENTE_NPC_PESSOAL>",
    ):
        assert tag in system
    assert "não à trama global" not in system
    assert "não cite personagens nomeados" not in system
    assert "thread_refs" in system and "NA BORDA" in system


def test_backstory_wrapped_as_player_input(monkeypatch):
    llm = _Capture()
    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: llm)
    prologue.build_start_scenario_ctx(CHAR)
    human = llm.messages[1].content
    assert "<entrada_do_jogador>" in human and "Aranel</entrada_do_jogador>" in human
    assert "nunca instrução" in llm.messages[0].content


def _raw(**over) -> StartScenario:
    base = dict(
        prologue="p", opening_scene_brief="b", arc_title="t", beats=["a", "b", "c"], climax="c"
    )
    base.update(over)
    return StartScenario(**base)


def test_normalize_drops_refs_outside_menu():
    menu = _menu()
    good = menu["doors"][1]["door_id"]
    out = prologue._normalize(_raw(thread_refs=["inventada", good, "outra"]), CHAR, menu)
    assert out.thread_refs == [good]
    out = prologue._normalize(_raw(thread_refs=["inventada"]), CHAR, menu)
    assert out.thread_refs == [menu["doors"][0]["door_id"]]


def test_plot_npc_from_graph_not_llm():
    menu = _menu()
    out = prologue._normalize(_raw(plot_npc_id="npc_inventado", plot_npc_hook="x"), CHAR, menu)
    assert out.plot_npc_id == menu["npcs"][0]["entity_id"]
    empty = dict(menu, npcs=[])
    out = prologue._normalize(_raw(plot_npc_id="npc_x", plot_npc_hook="x"), CHAR, empty)
    assert out.plot_npc_id == "" and out.plot_npc_hook == ""


def test_exactly_one_personal_and_one_plot():
    scenario, _mock, ctx = prologue.build_start_scenario_ctx(CHAR)
    d = scenario.model_dump()
    assert d["personal_npc"] and d["plot_npc_id"]
    assert oc.check_npc_cardinality(d, ctx["menu"]).ok
    assert [n.kind for n in scenario.seed_npcs] == ["personal"]


def test_fallback_template_linked_to_first_door(monkeypatch):
    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: FallbackLLM("sem provider"))
    scenario, mock, ctx = prologue.build_start_scenario_ctx(CHAR)
    menu = ctx["menu"]
    assert mock is False and ctx["template"] is True
    assert scenario.thread_refs == [menu["doors"][0]["door_id"]]
    assert scenario.plot_npc_id == menu["npcs"][0]["entity_id"]
    assert scenario.personal_npc is None
    d = scenario.model_dump()
    assert oc.check_thread_linked(d, menu).ok
    assert oc.check_npc_cardinality(d, menu, template=True).ok
    assert oc.check_seeking_present(d).ok and oc.check_starts_at_edge(d).ok


def test_mock_path_passes_opening_checks():
    scenario, _mock, ctx = prologue.build_start_scenario_ctx(CHAR)
    results = oc.run_all(
        scenario.model_dump(), ctx["menu"], character_name=CHAR["name"], backstory=CHAR["backstory"]
    )
    failed = [r for r in results if not r.ok]
    assert not failed, failed


def test_flag_off_keeps_legacy_prompt_and_seed(monkeypatch):
    monkeypatch.setenv("RPG_OPENING_THREAD", "off")
    llm = _Capture()
    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: llm)
    scenario, _m, ctx = prologue.build_start_scenario_ctx(CHAR)
    system = llm.messages[0].content
    assert "<PORTAS_DE_TRAMA>" not in system and "não à trama global" in system
    assert ctx["menu"] is None and ctx["nonce"] == ""
    assert scenario.thread_refs == [] and scenario.personal_npc is None


def test_flag_off_mock_keeps_legacy_fixture(monkeypatch):
    monkeypatch.setenv("RPG_OPENING_THREAD", "off")
    scenario, _mock = prologue.build_start_scenario(CHAR)
    seed = prologue.scenario_to_state_seed(scenario, {**CHAR, "game_id": "g"}, "nova_arcadia")
    assert "opening_thread" not in seed["campaign_plan"]
    assert scenario.seed_npcs[0].name in seed["npcs"]


def test_flag_shadow_logs_and_keeps_legacy_prompt(monkeypatch):
    monkeypatch.setenv("RPG_OPENING_THREAD", "shadow")
    logged = []
    monkeypatch.setattr(prologue, "_log_event", lambda *a, **k: logged.append((a, k)))
    llm = _Capture()
    monkeypatch.setattr(prologue, "get_llm", lambda *a, **k: llm)
    prologue.build_start_scenario_ctx(CHAR)
    assert "<PORTAS_DE_TRAMA>" not in llm.messages[0].content
    assert any(a[1] == "thread.shadow" for a, _k in logged)


def test_personal_attitude_and_overflow_sanitised():
    menu = _menu()
    p = PersonalNPC(
        name="  Ilva  ",
        role_public="r" * 200,
        persona_public="p",
        appearance="a",
        legend="l" * 400,
        bond="b",
        attitude="Aliado cauteloso",
    )
    out = prologue._normalize(_raw(personal_npc=p), CHAR, menu)
    assert out.personal_npc.name == "Ilva" and out.personal_npc.attitude == "neutro"
    assert len(out.personal_npc.role_public) == 80 and len(out.personal_npc.legend) == 160
    prologue.StartScenarioIn(**out.model_dump())  # passa a re-validação estrita
