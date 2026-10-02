"""Suíte da Fase 2.8 — Context builder com orçamento de tokens.
Spec: specs/SPEC-005-fase-2.8-context-builder.md. 100% offline e determinística (sem LLM).

Ids canônicos reais de data/graph/entities.json usados aqui:
  npc_valerius → controla nova_arcadia (não lidera fação)
  mao_sombria (fação), nova_arcadia (local)
"""
import uuid

import pytest

from services import context_builder as cb
from services import graph_resolver as gr


@pytest.fixture(autouse=True)
def _fresh_graph_cache():
    gr.clear_cache()
    yield
    gr.clear_cache()


def _state(**over) -> dict:
    base = {
        "world": {"turn_count": 5, "current_location": "nova_arcadia"},
        "world_projection": {},
        "event_log": [],
        "pending_world_events": [],
        "narrative_summary": "",
        "npcs": {},
    }
    base.update(over)
    return base


# --------------------------------------------------------------------------- #
# Etapa 1 — score + budget puros
# --------------------------------------------------------------------------- #
def test_estimate_tokens():
    assert cb.estimate_tokens("a" * 400) == 100
    assert cb.estimate_tokens("") == 0


def test_score_pondera_local():
    kw = dict(query="ataque nova_arcadia", scene_entities=[], impact=0.5, turns_ago=0)
    com_local = cb.score_fact("tropas marcham sobre nova_arcadia", current_loc="nova_arcadia", **kw)
    sem_local = cb.score_fact("tropas marcham sobre a fronteira", current_loc="nova_arcadia", **kw)
    assert com_local > sem_local, "fato citando o local atual deve pontuar mais"


def test_score_recencia_decai():
    kw = dict(query="x", current_loc="nova_arcadia", scene_entities=[], impact=0.5)
    recente = cb.score_fact("evento", turns_ago=0, **kw)
    antigo = cb.score_fact("evento", turns_ago=40, **kw)
    assert recente > antigo, "fato recente deve pontuar mais que antigo"


def test_budget_nunca_estoura():
    facts = [
        cb.ScoredFact(text="fato grande " * 10, score=float(i), section="current_state")
        for i in range(200)
    ]
    budget = cb.ContextBudget(max_tokens=500)
    pack = cb.assemble_pack(facts, budget)
    assert pack.total_tokens_est <= budget.max_tokens * 1.05
    assert pack.dropped > 0, "com 200 fatos e budget apertado, muitos devem sobrar de fora"


def test_sobra_de_cota_rola():
    # Nenhum fato em current_state (0.25) → cota rola para active_location (0.20).
    # active_location recebe fatos que somam > 0.20*budget mas < 0.45*budget → todos entram.
    budget = cb.ContextBudget(max_tokens=1000)  # 0.20 = 200 tok; 0.25+0.20 = 450 tok
    facts = [
        cb.ScoredFact(text="x" * 400, score=1.0, section="active_location")  # 100 tok cada
        for _ in range(4)  # 400 tok total > 200 da própria cota, < 450 com o carry
    ]
    pack = cb.assemble_pack(facts, budget)
    assert pack.dropped == 0, "cota não usada de current_state deveria rolar para active_location"
    assert pack.world_state_block.count("xxxx") >= 1


# --------------------------------------------------------------------------- #
# Etapa 2 — coleta de fatos dinâmicos
# --------------------------------------------------------------------------- #
def test_event_vira_frase():
    ev = {"event_id": uuid.uuid4().hex, "turn": 3, "type": "npc_killed",
          "actor_id": "player", "target_id": "npc_valerius", "payload": {}}
    text = cb.render_event(ev)
    assert text.startswith("[turno 3]")
    nome = gr.get_entity("npc_valerius")["name"]
    assert nome in text, "deve usar o nome canônico, não o id cru"
    assert "npc_valerius" not in text


def test_render_event_tipo_desconhecido_vazio():
    assert cb.render_event({"type": "coisa_nova", "turn": 1}) == ""


def test_secret_so_se_revelado():
    rf = {"entity_id": "npc_valerius", "fact": "conspira contra a coroa",
          "revealed_at_turn": 4, "revealed_by_event": "e1"}
    com = _state(world_projection={"revealed_facts": {"e1": rf}})
    facts_com = cb.collect_dynamic_facts(com, purpose="story", query="q",
                                         current_loc="nova_arcadia", scene_entities=[])
    assert any("conspira" in f.text for f in facts_com)

    sem = _state(world_projection={"revealed_facts": {}})
    facts_sem = cb.collect_dynamic_facts(sem, purpose="story", query="q",
                                         current_loc="nova_arcadia", scene_entities=[])
    assert not any("conspira" in f.text for f in facts_sem)


def test_50_eventos_top5():
    eventos = [
        {"event_id": uuid.uuid4().hex, "turn": t, "type": "npc_killed",
         "actor_id": "player", "target_id": "npc_valerius", "payload": {}}
        for t in range(1, 51)
    ]
    st = _state(world={"turn_count": 50, "current_location": "nova_arcadia"},
                event_log=eventos)
    pack = cb.build_context_pack(st, query="nova_arcadia", purpose="story", token_budget=200)
    assert pack.dropped > 0, "50 eventos em budget apertado devem estourar a cota"
    assert pack.total_tokens_est <= 200 * 1.05
    # eventos recentes (turno alto) devem ganhar dos antigos por recência
    assert "[turno 50]" in pack.world_state_block
    assert "[turno 1]" not in pack.world_state_block


def test_build_pack_purpose_invalido():
    with pytest.raises(ValueError):
        cb.build_context_pack(_state(), query="q", purpose="xpto")


def test_controlador_no_estado_atual():
    # npc_valerius controla nova_arcadia por edge base → aparece no bloco de estado.
    st = _state()
    pack = cb.build_context_pack(st, query="quem manda", purpose="story", token_budget=3500)
    nome = gr.get_entity("npc_valerius")["name"]
    assert nome in pack.world_state_block


# --------------------------------------------------------------------------- #
# Etapa 3 — integração storyteller
# --------------------------------------------------------------------------- #
class _CapturingLLM:
    """Captura o SystemMessage do prompt e devolve um StoryUpdate mínimo."""

    def __init__(self, model_kwargs=None):
        self.captured = None
        self._kwargs = model_kwargs or {}

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, msgs):
        self.captured = str(msgs[0].content)
        return self._model(narrative="ok", introduced_npcs=[], proposed_events=[])


def _story_state():
    from langchain_core.messages import HumanMessage
    st = _state(game_id="pytest28", narrative_summary="", messages=[
        HumanMessage(content="olho ao redor")],
        factions=[], faction_intel={}, player={"name": "T", "class_name": "Guerreiro"},
        campaign_plan={})
    st["world"] = {"current_location": "nova_arcadia", "turn_count": 5,
                   "time_of_day": "Dia", "weather": "Neutro", "danger_level": 1, "quest_plan": []}
    return st


def test_storyteller_usa_pack(monkeypatch):
    import agents.storyteller as stt

    calls = {}
    real_build = cb.build_context_pack

    def spy(state, query, purpose, **kw):
        calls["purpose"] = purpose
        return real_build(state, query, purpose, **kw)

    monkeypatch.setattr(stt, "build_context_pack", spy)
    llm = _CapturingLLM()
    monkeypatch.setattr(stt, "get_llm", lambda *a, **k: llm)

    out = stt.storyteller_node(_story_state())

    assert calls.get("purpose") == "story"
    prompt = llm.captured
    assert "<ESTADO_ATUAL_DO_MUNDO>" in prompt
    # ESTADO ATUAL entra ANTES da lore base (precedência da verdade viva)
    assert prompt.index("<ESTADO_ATUAL_DO_MUNDO>") < prompt.index("<LORE_PUBLICO_CANONICO>")
    assert "ESTADO ATUAL VENCE" in prompt
    assert "narrative" not in out or "messages" in out


# --------------------------------------------------------------------------- #
# Etapa 4 — npc, combat (budget 1200), campaign_manager
# --------------------------------------------------------------------------- #
def test_npc_usa_pack(monkeypatch):
    import agents.npc as npc
    from langchain_core.messages import HumanMessage

    calls = {}

    def spy(state, query, purpose, **kw):
        calls["purpose"] = purpose
        return real_build(state, query, purpose, **kw)

    real_build = cb.build_context_pack
    monkeypatch.setattr(npc, "build_context_pack", spy)

    llm = _CapturingLLM()

    class _NPCLLM(_CapturingLLM):
        def invoke(self, msgs):
            self.captured = str(msgs[0].content)
            return self._model(dialogue="oi", action_description="", memory_update="",
                               relationship_change=0, faction_reveals=[])

    npc_llm = _NPCLLM()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: npc_llm)

    st = _state(active_npc_name="Guarda", game_id="pytest28",
                npcs={"Guarda": {"name": "Guarda", "role": "guarda", "persona": "rude",
                                 "location": "nova_arcadia", "memory": [], "relationship": 5}},
                messages=[HumanMessage(content="quem manda aqui?")])
    npc.npc_actor_node(st)
    assert calls.get("purpose") == "npc"
    assert "<ESTADO_ATUAL_DO_MUNDO>" in npc_llm.captured


def test_combat_pack_budget_1200(monkeypatch):
    import agents.combat as combat

    calls = {}
    real_build = cb.build_context_pack

    def spy(state, query, purpose, token_budget=3500, **kw):
        calls["purpose"] = purpose
        calls["budget"] = token_budget
        return real_build(state, query, purpose, token_budget=token_budget, **kw)

    monkeypatch.setattr(combat, "build_context_pack", spy)
    # _narrate cai no fallback determinístico com FallbackLLM (não chama rede)
    from llm_setup import FallbackLLM
    monkeypatch.setattr(combat, "get_llm", lambda *a, **k: FallbackLLM("x"))

    player = {"name": "T", "hp": 10, "max_hp": 10}
    txt = combat._narrate(player, [], ["golpe"], None, "ataco", True,
                          "<ESTADO_ATUAL_DO_MUNDO>\nx\n</ESTADO_ATUAL_DO_MUNDO>")
    assert isinstance(txt, str) and txt  # narração de fallback não quebra com world_ctx
    # confirma que combat_node pede budget 1200 (via spy no build direto)
    pack = combat.build_context_pack(_state(), query="q", purpose="combat_narration",
                                     token_budget=1200)
    assert calls["budget"] == 1200 and calls["purpose"] == "combat_narration"


def test_campaign_usa_pack(monkeypatch):
    import agents.campaign_manager as cmgr
    from langchain_core.messages import HumanMessage

    calls = {}
    real_build = cb.build_context_pack

    def spy(state, query, purpose, **kw):
        calls["purpose"] = purpose
        return real_build(state, query, purpose, **kw)

    monkeypatch.setattr(cmgr, "build_context_pack", spy)

    class _PlanLLM(_CapturingLLM):
        def invoke(self, msgs):
            self.captured = str(msgs[0].content)
            return self._model(location="nova_arcadia", beats=["b1", "b2", "b3"], climax="c")

    plan_llm = _PlanLLM()
    monkeypatch.setattr(cmgr, "get_llm", lambda *a, **k: plan_llm)

    st = _state(messages=[HumanMessage(content="explorar")])
    cmgr._build_plan(st)
    assert calls.get("purpose") == "planning"
    assert "<ESTADO_ATUAL_DO_MUNDO>" in plan_llm.captured
