"""SPEC-311 Etapas 3-4 — o planner vê o mundo percebido e o mundo muda o arco (R1-R9)."""

from __future__ import annotations

import re

import pytest
from langchain_core.messages import HumanMessage

import agents.campaign_manager as cm
import agents.storyteller as stt
from services import perceived_world as pw
from services import planner_context as pc
from tests.spec309_helpers import world_state_two_regions
from tests.test_ambient_consumers import _Spy, _story_state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("RPG_WORLD_ENGINE", "on")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")


def _q(title, **kw):
    return {"id": "q-" + title[:3], "title": title, "status": "active", **kw}


WORLD_Q = _q(
    "Defender os portões de Skallgard",
    origin_name="cartaz da guarda",
    world_kind="defesa",
    deadline_day=6,
    world_source_id="c1",
    heard_via="cartaz",
)
PLAIN_Q = _q("Entregar a carta de Brynja", origin_name="Brynja")


def _state(quests=()):
    st = world_state_two_regions()
    st.update(
        quests=list(quests), messages=[HumanMessage(content="olho em volta")], campaign_plan={}
    )
    st["world"].update(weather="neve", time_of_day="Manhã")
    return st


# --- R1: quests -----------------------------------------------------------------------------
def test_planner_quests_block_format_no_ids_no_proof():
    block = pc.planner_quests_block(_state([WORLD_Q, PLAIN_Q]))
    assert block.startswith("<QUESTS_DO_HEROI>") and block.endswith("</QUESTS_DO_HEROI>")
    lines = block.splitlines()[1:-1]
    assert lines[0] == (
        "- Defender os portões de Skallgard · origem: cartaz da guarda · tipo: mundo · prazo: "
        "urgente"
    )
    assert lines[1] == "- Entregar a carta de Brynja · origem: Brynja"
    assert "q-" not in block and "c1" not in block and "cartaz\n" not in block
    assert not re.search(r"\d", block)


def test_planner_quests_block_world_first_and_cap():
    many = [_q(f"Comum {i}") for i in range(10)] + [WORLD_Q]
    lines = pc.planner_quests_block(_state(many)).splitlines()[1:-1]
    assert len(lines) == pc.PLANNER_QUESTS_MAX
    assert "Defender os portões" in lines[0]
    assert "Comum 0" in lines[1]
    done = {**PLAIN_Q, "status": "completed"}
    assert pc.planner_quests_block(_state([done])) == ""


def test_planner_quests_block_empty_when_none():
    assert pc.planner_quests_block(_state([])) == ""
    assert pc.planner_quests_block({}) == ""


# --- prompt do planner ----------------------------------------------------------------------
class _PlanLLM:
    def __init__(self):
        self.prompts: list[str] = []

    def with_structured_output(self, _model):
        return self

    def invoke(self, msgs, *_a, **_k):
        self.prompts.append("\n".join(str(getattr(m, "content", m)) for m in msgs))
        return cm.CampaignPlanModel(
            location="Skallgard",
            beats=["Um gancho", "Dois gancho", "Tres gancho"],
            climax="Fim",
            arc_title="Arco de Teste",
        )


def _plan_prompt(monkeypatch, st) -> str:
    llm = _PlanLLM()
    monkeypatch.setattr(cm, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(
        cm,
        "build_context_pack",
        lambda *a, **k: type("Pack", (), {"lore_block": "", "world_state_block": "<W/>"})(),
    )
    cm._build_plan(st)
    return llm.prompts[0]


def test_planner_prompt_has_heard_and_quests(monkeypatch):
    st = _state([WORLD_Q])
    st["world"]["news"] = [{"day": 4, "location_name": "Skallgard", "text": "Guerra à vista."}]
    prompt = _plan_prompt(monkeypatch, st)
    assert "<OUVIU_DIZER>" in prompt and "Guerra à vista." in prompt
    assert "<QUESTS_DO_HEROI>" in prompt and "Defender os portões" in prompt
    assert prompt.index("<W/>") < prompt.index("<OUVIU_DIZER>") < prompt.index("<QUESTS_DO_HEROI>")
    assert prompt.index("<QUESTS_DO_HEROI>") < prompt.index("<LORE_CONTEXT>")
    assert cm.PLANNER_WORLD_INSTRUCTION in prompt


def test_planner_instruction_only_with_blocks(monkeypatch):
    st = _state([])
    st["world_projection"] = {}
    st["event_log"] = []
    st["world"]["news"] = []
    prompt = _plan_prompt(monkeypatch, st)
    assert cm.PLANNER_WORLD_INSTRUCTION not in prompt
    assert "QUESTS_DO_HEROI" not in prompt and "OUVIU_DIZER" not in prompt


# --- R6: gatilho ----------------------------------------------------------------------------
CRISE = {"kind": "crise", "region_id": "skallgard", "template_id": "fome.crise.inicio"}
QUEDA = {"kind": "escala", "region_id": "skallgard", "template_id": "ocupado.crise.escala"}
QUEDA_BREKMAR = {"kind": "escala", "region_id": "brekmar", "template_id": "ocupado.crise.escala"}
QFAIL = {"type": "quest_failed", "target_id": "q"}


def test_world_replan_cause_crise_regiao():
    assert pc.world_replan_cause(_state(), [CRISE], []) == "crise_regiao"


def test_world_replan_cause_queda_cidade_regiao_atual():
    assert pc.world_replan_cause(_state(), [QUEDA], []) == "queda_cidade"
    ruina = {**QUEDA, "template_id": "ruina.crise.escala"}
    assert pc.world_replan_cause(_state(), [ruina], []) == "queda_cidade"


def test_world_replan_cause_queda_outra_regiao_none():
    """D1: queda de cidade em outra região não replaneja."""
    assert pc.world_replan_cause(_state(), [QUEDA_BREKMAR], []) is None
    other_crisis = {**CRISE, "region_id": "brekmar"}
    assert pc.world_replan_cause(_state(), [other_crisis], []) is None


def test_world_replan_cause_quest_falhou():
    assert pc.world_replan_cause(_state(), [], [QFAIL]) == "quest_falhou"
    assert pc.world_replan_cause(_state(), [], [{"type": "quest_offered"}]) is None


def test_world_replan_cause_priority_order():
    assert pc.world_replan_cause(_state(), [QUEDA, CRISE], [QFAIL]) == "crise_regiao"
    assert pc.world_replan_cause(_state(), [QUEDA], [QFAIL]) == "queda_cidade"


def test_world_replan_cause_ignores_unperceived_crisis():
    """Oráculo §3.6 (2): crise aberta em world_sim que ninguém percebeu não dispara."""
    st = _state()
    st["world_sim"]["crises"] = [{"crisis_id": "c-fome", "kind": "fome", "region_id": "skallgard"}]
    assert pc.world_replan_cause(st, [], []) is None
    assert pc.world_replan_cause(st, [QUEDA_BREKMAR], []) is None
    assert pc.world_replan_cause(st, [CRISE], []) == "crise_regiao"


def test_world_replan_cause_never_raises():
    assert pc.world_replan_cause({}, [None, "x"], [None]) is None  # type: ignore[list-item]


# --- R7/R8/R9: costura no storyteller -------------------------------------------------------
def _run_story(monkeypatch, cause, llm=None):
    logs: list[tuple] = []
    monkeypatch.setattr(pc, "world_replan_cause", lambda *a, **k: cause)
    monkeypatch.setattr(stt, "_log_event", lambda *a, **k: logs.append((a, k)))
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm or _Spy())
    out = stt.storyteller_node(_story_state())
    return out, logs


def test_storyteller_sets_needs_replan_on_trigger(monkeypatch):
    out, logs = _run_story(monkeypatch, "crise_regiao")
    assert out["needs_replan"] is True
    assert (("campaign", "world_replan_trigger"), {"cause": "crise_regiao"}) in logs


def test_storyteller_no_trigger_no_replan(monkeypatch):
    out, logs = _run_story(monkeypatch, None)
    assert not out.get("needs_replan")
    assert not any(a[:2] == ("campaign", "world_replan_trigger") for a, _k in logs)


def test_storyteller_trigger_survives_llm_failure(monkeypatch):
    """R7: o caminho de fallback (LLM quebrou) também leva o gatilho."""

    class _Boom:
        is_fallback = False

        def with_structured_output(self, *_a, **_k):
            return self

        def invoke(self, *_a, **_k):
            raise RuntimeError("boom")

    out, _logs = _run_story(monkeypatch, "queda_cidade", llm=_Boom())
    assert out["needs_replan"] is True


def test_trigger_logs_closed_enum(monkeypatch):
    for cause in ("crise_regiao", "queda_cidade", "quest_falhou"):
        _out, logs = _run_story(monkeypatch, cause)
        hits = [k for a, k in logs if a[:2] == ("campaign", "world_replan_trigger")]
        assert hits == [{"cause": cause}]
        assert not any(c.isdigit() for c in cause)


def test_trigger_inert_engine_off_and_quests_shadow(monkeypatch):
    """R9: sem motor `on` não há itens percebidos; sem quests `on`, não há quest_failed."""
    monkeypatch.setenv("RPG_WORLD_ENGINE", "off")
    monkeypatch.setenv("RPG_WORLD_QUESTS", "shadow")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy())
    out = stt.storyteller_node(_story_state())
    assert not out.get("needs_replan")


# --- Etapa 4: <MUNDO_PERCEBIDO> no planner --------------------------------------------------
def test_perceived_world_planning_audience_lines():
    st = _state()
    st["world_projection"]["location_states"]["skallgard"] = {"state": "cerco", "severity": 2}
    lines = pw.perceived_world_lines(st, audience="planning")
    assert "Skallgard está sitiada." in lines
    assert any(line.startswith("Há sinais de fome") for line in lines)


def test_planner_prompt_has_perceived_world(monkeypatch):
    st = _state()
    st["world_projection"]["location_states"]["skallgard"] = {"state": "cerco", "severity": 2}
    prompt = _plan_prompt(monkeypatch, st)
    assert "<MUNDO_PERCEBIDO>" in prompt and "Skallgard está sitiada." in prompt
    assert prompt.index("<W/>") < prompt.index("<MUNDO_PERCEBIDO>")
    assert cm.PLANNER_WORLD_INSTRUCTION in prompt


def test_planner_golden_rule_oracle(monkeypatch):
    """§3.6 (1): o prompt inteiro do planner não vaza o que o herói não percebeu."""
    st = _state([PLAIN_Q])
    st["world_sim"]["pressures"] = {"brekmar": {"guerra": 77}}
    st["world_sim"]["bands"] = {"brekmar": {"guerra": "crise"}}
    st["world_sim"]["crises"] = [{"crisis_id": "c-secreta", "kind": "fome", "region_id": "brekmar"}]
    prompt = _plan_prompt(monkeypatch, st)
    low = prompt.lower()
    assert "brekmar" not in low and "sitiada" not in low
    for forbidden in ("pressures", "bands", "world_sim", "c-secreta", "c-siege", "severity"):
        assert forbidden not in prompt
    assert "Zedrik" not in prompt


def test_perceived_world_planning_budget():
    st = _state()
    st["world_projection"]["location_states"]["skallgard"] = {"state": "cerco", "severity": 2}
    lines = pw.perceived_world_lines(st, audience="planning")
    assert len(lines) <= pw.MAX_LINES
    from services.context_builder import estimate_tokens

    assert estimate_tokens(pw.perceived_world_block(st, audience="planning")) <= pw.MAX_TOKENS + 40


def test_storyteller_trigger_survives_ambush_early_return(monkeypatch):
    """R7 (P2-3): o retorno antecipado de emboscada leva o gatilho do mundo."""
    enc = {"reason": "controlled", "flavor": "Eles surgem.", "hint": "lobo", "enemy_id": ""}
    monkeypatch.setattr(stt, "check_encounter", lambda *a, **k: dict(enc))
    monkeypatch.setattr(pc, "world_replan_cause", lambda *a, **k: "crise_regiao")
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: _Spy())
    st = _story_state(text="Viajo para as Montanhas Afiadas")
    st["world"]["visited"] = ["skallgard", "montanhas_afiadas"]
    out = stt.storyteller_node(st)
    assert out.get("next") == "combat_agent", out.keys()
    assert out["needs_replan"] is True
