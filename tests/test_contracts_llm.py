"""Fase 11 — LLM contract tests: o provider REAL respeita os contratos de shape
que o motor assume. MockLLM devolve Pydantic válido e esconde bug de mapeamento
— esta suíte roda contra o Gemini de verdade.

Rodar:  uv run pytest -m llm_contract -v -s
Orçamento total: ~13 requests (free tier = 20/dia/modelo). O contrato de
fallback roda SEM chave (offline). Fora do CI padrão (addopts -m "not llm_contract").

Spec: specs/fase-11-llm-contract-tests.md. Substitui tests/test_real_llm.py.
"""
import os

import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

load_dotenv(override=True)  # chave vive no .env, não no ambiente do SO

pytestmark = pytest.mark.llm_contract

_needs_key = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY não definida — contratos de provider real pulados",
)

import world_utils as wu
from agents.combat import combat_node
from agents.npc import npc_actor_node
from agents.loot import loot_node
from main import app


_FALLBACK_SIGNATURE = "narrador está indisponível"


def _no_fallback(result: dict) -> bool:
    """False se qualquer mensagem/resumo carrega a assinatura do FallbackLLM."""
    for msg in result.get("messages", []):
        content = getattr(msg, "content", "") or ""
        if _FALLBACK_SIGNATURE in content:
            return False
    if _FALLBACK_SIGNATURE in (result.get("narrative_summary", "") or ""):
        return False
    return True


def _base_state(**overrides) -> dict:
    state = {
        "game_id": "contract_llm_test",
        "narrative_summary": "O herói Aldric chegou à cidade de Nova Arcádia.",
        "archivist_last_run": 0,
        "chronicle": [],
        "messages": [HumanMessage(content="Quero explorar o mercado da cidade.")],
        "next": None,
        "player": {
            "name": "Aldric", "class_name": "Guerreiro", "race": "Humano",
            "hp": 30, "max_hp": 30, "mana": 5, "max_mana": 5,
            "stamina": 15, "max_stamina": 15,
            "gold": 50, "level": 1, "xp": 0, "alignment": "Neutro",
            "attributes": {"str": 14, "dex": 10, "con": 12, "int": 8, "wis": 10, "cha": 10},
            # formato 4.3 ({id, qty}) — save real chega migrado; string legada
            # quebraria add_item (achado do primeiro run desta suíte)
            "inventory": [{"id": "espada_curta", "qty": 1}],
            "known_abilities": ["ataque_basico"],
            "defense": 12, "attack_bonus": 3,
            "active_conditions": [], "ability_cooldowns": {},
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "campaign_plan": None, "needs_replan": True,
        "enemies": [], "party": [], "npcs": {},
        "active_npc_name": None, "active_plan_step": None,
        "router_confidence": None, "last_routed_intent": None,
        "combat_target": None, "loot_source": None, "combat": None,
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def use_real_llm(monkeypatch):
    """Opt-out do RPG_FORCE_MOCK que tests/conftest.py força na suíte offline."""
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)


@pytest.fixture(scope="session", autouse=True)
def _request_counter():
    """R5: conta chamadas de get_llm (proxy de requests) e imprime no fim."""
    import llm_setup
    contagem = {"n": 0}
    original = llm_setup.get_llm

    def contado(*args, **kwargs):
        contagem["n"] += 1
        return original(*args, **kwargs)

    llm_setup.get_llm = contado
    yield
    llm_setup.get_llm = original
    print(f"\n[CONTRACT] ~{contagem['n']} instâncias de LLM pedidas (proxy de requests)")


# ---------------------------------------------------------------------------
# Contrato 1-2 — Router classifica intenção  (_BUDGET: 2 requests FAST)
# ---------------------------------------------------------------------------

@_needs_key
def test_router_classifica_combate():
    from agents.router import dm_router_node

    state = _base_state(messages=[HumanMessage(
        content="Desembainho a espada e ataco o goblin à minha frente!")])
    out = dm_router_node(state)
    assert out.get("next") == "combat_agent", f"router mandou para {out.get('next')}"


@_needs_key
def test_router_classifica_npc_com_alvo():
    from agents.router import dm_router_node

    vendedor = {"name": "Vendedor Misterioso", "role": "Comerciante",
                "persona": "Enigmático", "location": "Nova Arcádia",
                "relationship": 5, "memory": [], "in_scene": True}
    state = _base_state(
        messages=[HumanMessage(content='Falo com o Vendedor Misterioso: "o que vende hoje?"')],
        npcs={"Vendedor Misterioso": vendedor})
    out = dm_router_node(state)
    assert out.get("next") == "npc_actor", f"router mandou para {out.get('next')}"
    assert out.get("active_npc_name") == "Vendedor Misterioso"


# ---------------------------------------------------------------------------
# Contrato 3 — StoryUpdate: turno banal não alucina evento  (_BUDGET: 1 FAST)
# ---------------------------------------------------------------------------

@_needs_key
def test_storyupdate_banal_sem_eventos():
    from agents.storyteller import StoryUpdate
    from llm_setup import ModelTier, get_llm

    llm = get_llm(temperature=0.4, tier=ModelTier.FAST)
    engine = llm.with_structured_output(StoryUpdate)
    res = engine.invoke([HumanMessage(content=(
        "Narre em 2 frases: o jogador olha as nuvens na praça de Nova Arcádia "
        "e boceja. Nada de importante acontece."))])
    # R4: se o provider caiu no fallback, falha LEGÍVEL
    assert isinstance(res, StoryUpdate), "provider caiu no fallback — quota?"
    assert res.proposed_events == [], "turno banal alucinou evento de mundo"
    assert res.narrative.strip()


# ---------------------------------------------------------------------------
# Contrato 4 — Combate: parse + narração  (_BUDGET: ~2 requests)
# ---------------------------------------------------------------------------

@_needs_key
def test_combat_node_direct():
    goblin = {
        "id": "goblin_1", "name": "Goblin", "hp": 12, "max_hp": 12,
        "stamina": 5, "mana": 0, "defense": 11, "attack_mod": 2,
        "attributes": {"str": 8, "dex": 14, "con": 10, "int": 6, "wis": 8, "cha": 6},
        "abilities": [], "status": "ativo", "active_conditions": [],
        "attacks": [{"name": "Adaga", "bonus": 2, "damage": "1d4"}],
    }
    state = _base_state(
        messages=[HumanMessage(content="ataco o goblin com minha espada longa")],
        enemies=[goblin], combat=None)

    result = combat_node(state)

    assert isinstance(result, dict) and result
    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip()
    assert "enemies" in result
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Contrato 5 — NPC não-onisciência  (_BUDGET: ~1 SMART)
# ---------------------------------------------------------------------------

@_needs_key
def test_npc_nao_onisciente():
    """Fato sintético existe no estado mas FORA do contexto do NPC — a resposta
    não pode conter a palavra (verificável por substring, zero ambiguidade)."""
    segredo = "ZIMBRAZUL"  # palavra inventada: só sai se vazar do estado
    vendedor = {
        "id": "npc_vendedor_misterioso", "name": "Vendedor Misterioso",
        "role": "Comerciante de Raridades", "location": "Nova Arcádia",
        "persona": "Fala em enigmas, nunca revela a origem dos itens.",
        "relationship": 5, "memory": [], "in_scene": True,
        "attributes": {"str": 8, "dex": 12, "con": 10, "int": 16, "wis": 14, "cha": 18},
        "combat_stats": {"hp": 8, "ac": 10, "attacks": []},
    }
    state = _base_state(
        messages=[HumanMessage(content="Qual é a senha do cofre do banco?")],
        npcs={"Vendedor Misterioso": vendedor},
        active_npc_name="Vendedor Misterioso")
    # o fato vive num canto do estado que o npc_actor NÃO injeta no prompt
    state["_segredo_de_teste"] = f"a senha do cofre é {segredo}"

    result = npc_actor_node(state)

    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip()
    assert segredo not in ai_msg.content, "NPC vazou fato fora do próprio contexto"
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Contrato 6 — TradeIntent mapeia compra  (_BUDGET: 1 FAST)
# ---------------------------------------------------------------------------

@_needs_key
def test_trade_intent_compra():
    from agents.loot import TradeIntent
    from llm_setup import ModelTier, get_llm

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    engine = llm.with_structured_output(TradeIntent)
    res = engine.invoke([HumanMessage(content=(
        "O jogador disse ao mercador: 'compro duas poções de cura'. "
        "Extraia a transação."))])
    assert isinstance(res, TradeIntent), "provider caiu no fallback — quota?"
    assert res.mode == "buy"
    assert res.qty == 2
    assert "po" in res.item_ref.lower()  # "poção/pocao de cura"


# ---------------------------------------------------------------------------
# Contrato 7 — E2E rota story + archivist  (_BUDGET: ~4 requests)
# ---------------------------------------------------------------------------

@_needs_key
def test_e2e_story_route():
    state = _base_state(archive_due=True)
    result = app.invoke(state)

    assert result.get("campaign_plan"), "campaign_manager deve gerar plano"
    assert len(result["campaign_plan"].get("beats", [])) >= 1

    summary = result.get("narrative_summary", "")
    assert summary, "archivist deve manter um narrative_summary"
    assert int(result.get("archivist_last_run", 0)) > 0, \
        "archivist não rodou neste turno (cadência/archive_due)"

    ai_msgs = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
    assert ai_msgs and ai_msgs[-1].content.strip()
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Contrato 8 — Loot narra tesouro  (_BUDGET: ~1 SMART)
# ---------------------------------------------------------------------------

@_needs_key
def test_loot_node_direct():
    goblin_morto = {
        "id": "goblin_morto", "name": "Goblin", "hp": 0, "max_hp": 12,
        "stamina": 0, "mana": 0, "defense": 11, "attack_mod": 2,
        "attributes": {"str": 8, "dex": 14, "con": 10, "int": 6, "wis": 8, "cha": 6},
        "abilities": [], "status": "morto", "active_conditions": [], "attacks": [],
    }
    state = _base_state(
        messages=[HumanMessage(content="vasculho o corpo do goblin em busca de itens valiosos")],
        loot_source="TREASURE", enemies=[goblin_morto])

    result = loot_node(state)

    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip()
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Contrato 9 — Fallback: turno sobrevive sem provider  (_BUDGET: 0 — offline)
# ---------------------------------------------------------------------------

def test_fallback_turno_sobrevive(monkeypatch):
    """RPG_NO_MOCK=1 força o FallbackLLM: o turno completa com mensagem digna e
    estado íntegro — nenhum AttributeError de structured output sem guard."""
    from agents.storyteller import storyteller_node

    monkeypatch.setenv("RPG_NO_MOCK", "1")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    state = _base_state(campaign_plan={"beats": [], "current_step": 0})
    out = storyteller_node(state)

    assert out.get("messages"), "turno com fallback precisa devolver mensagem"
    content = out["messages"][-1].content
    assert isinstance(content, str) and content.strip()
    # estado não corrompido: nada de exceção, dict parcial válido
    assert isinstance(out, dict)
