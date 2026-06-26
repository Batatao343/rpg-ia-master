"""
tests/test_real_llm.py

Harness frugal para validar o caminho do Gemini real.
~7-10 chamadas LLM no total (bem abaixo dos 20/dia free tier).

Execute com: uv run pytest tests/test_real_llm.py -v -s
Skip automático se GOOGLE_API_KEY não estiver definida.
"""
import os
import pytest
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

# Carrega .env antes do skip check (a chave está no .env, não no ambiente do SO)
load_dotenv(override=True)

pytestmark = pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY não definida — rode a suite offline: uv run pytest tests/test_mvp.py tests/test_fase0.py",
)

import world_utils as wu
from agents.combat import combat_node
from agents.npc import npc_actor_node
from agents.loot import loot_node
from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_FALLBACK_SIGNATURE = "narrador está indisponível"


def _no_fallback(result: dict) -> bool:
    """Retorna False se qualquer mensagem ou resumo carrega a assinatura do FallbackLLM."""
    for msg in result.get("messages", []):
        content = getattr(msg, "content", "") or ""
        if _FALLBACK_SIGNATURE in content:
            return False
    if _FALLBACK_SIGNATURE in (result.get("narrative_summary", "") or ""):
        return False
    return True


def _base_state(**overrides) -> dict:
    state = {
        "game_id": "real_llm_test",
        "narrative_summary": "O herói Aldric chegou à cidade de Nova Arcádia.",
        "archivist_last_run": 0,
        "chronicle": [],
        "messages": [HumanMessage(content="Quero explorar o mercado da cidade.")],
        "next": None,
        "player": {
            "name": "Aldric",
            "class_name": "Guerreiro",
            "race": "Humano",
            "hp": 30, "max_hp": 30,
            "mana": 5, "max_mana": 5,
            "stamina": 15, "max_stamina": 15,
            "gold": 50, "level": 1, "xp": 0,
            "alignment": "Neutro",
            "attributes": {"str": 14, "dex": 10, "con": 12, "int": 8, "wis": 10, "cha": 10},
            "inventory": ["Espada Longa", "Escudo de Madeira"],
            "known_abilities": ["ataque_basico"],
            "defense": 12,
            "attack_bonus": 3,
            "active_conditions": [],
            "ability_cooldowns": {},
        },
        "world": wu.starting_world("Nova Arcádia", 1),
        "campaign_plan": None,
        "needs_replan": True,
        "enemies": [],
        "party": [],
        "npcs": {},
        "active_npc_name": None,
        "active_plan_step": None,
        "router_confidence": None,
        "last_routed_intent": None,
        "combat_target": None,
        "loot_source": None,
        "combat": None,
    }
    state.update(overrides)
    return state


@pytest.fixture(autouse=True)
def use_real_llm(monkeypatch):
    """Remove RPG_FORCE_MOCK — tests/conftest.py o força; este fixture desfaz para a suite real."""
    monkeypatch.delenv("RPG_FORCE_MOCK", raising=False)


# ---------------------------------------------------------------------------
# Teste 1: E2E rota story completa
# Nós cobertos: campaign_manager(SMART) → router(FAST) → storyteller(FAST) → archivist(SMART)
# ~4 chamadas LLM
# ---------------------------------------------------------------------------
def test_e2e_story_route():
    initial_summary = "O herói Aldric chegou à cidade de Nova Arcádia."
    # Archivist agora roda com cadência (evento relevante OU a cada 10 turnos). Marcamos
    # archive_due=True para exercitar o caminho real do arquivista neste turno.
    state = _base_state(archive_due=True)
    result = app.invoke(state)

    assert result.get("campaign_plan"), "campaign_manager deve gerar plano"
    beats = result["campaign_plan"].get("beats", [])
    assert len(beats) >= 1, "plano deve ter ao menos 1 beat"

    summary = result.get("narrative_summary", "")
    assert summary, "archivist deve manter um narrative_summary"
    # Robusto à variância do Gemini (que pode degradar/ecoar): provamos que o ARCHIVIST
    # EXECUTOU neste turno (cadência via archive_due) — last_run avança do 0 inicial.
    assert int(result.get("archivist_last_run", 0)) > 0, (
        "archivist não rodou neste turno (cadência/archive_due) — ver logs '⚠️ [ARCHIVIST]'"
    )

    ai_msgs = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
    assert ai_msgs, "storyteller deve produzir ao menos 1 AIMessage"
    assert ai_msgs[-1].content.strip(), "resposta do storyteller não pode ser vazia"

    assert _no_fallback(result), "FallbackLLM detectado — guards falharam ou chave inválida"


# ---------------------------------------------------------------------------
# Teste 2: combat_node direto
# Inimigo já presente → sem spawn → parse(FAST) + narrate(SMART) ≈ 2 chamadas
# ---------------------------------------------------------------------------
def test_combat_node_direct():
    goblin = {
        "id": "goblin_1",
        "name": "Goblin",
        "hp": 12, "max_hp": 12,
        "stamina": 5, "mana": 0,
        "defense": 11, "attack_mod": 2,
        "attributes": {"str": 8, "dex": 14, "con": 10, "int": 6, "wis": 8, "cha": 6},
        "abilities": [],
        "status": "ativo",
        "active_conditions": [],
        "attacks": [{"name": "Adaga", "bonus": 2, "damage": "1d4"}],
    }
    state = _base_state(
        messages=[HumanMessage(content="ataco o goblin com minha espada longa")],
        enemies=[goblin],
        combat=None,
    )

    result = combat_node(state)

    assert isinstance(result, dict) and result, "combat_node deve retornar dict não-vazio"
    assert result.get("messages"), "deve conter ao menos 1 mensagem"
    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip(), "narração de combate vazia"
    assert "enemies" in result, "estado dos inimigos deve ser retornado"
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Teste 3: npc_actor_node direto
# NPC já no dict → sem generate_new_npc → ~1 SMART call
# ---------------------------------------------------------------------------
def test_npc_actor_node_direct():
    vendedor = {
        "id": "npc_vendedor_misterioso",
        "name": "Vendedor Misterioso",
        "role": "Comerciante de Raridades",
        "location": "Nova Arcádia",
        "persona": "Fala em enigmas, sempre sorri, nunca revela a origem dos itens.",
        "appearance": "Capa escura e chapéu largo.",
        "initial_relationship": 5,
        "relationship": 5,
        "memory": [],
        "attributes": {"str": 8, "dex": 12, "con": 10, "int": 16, "wis": 14, "cha": 18},
        "combat_stats": {"hp": 8, "ac": 10, "attacks": []},
    }
    state = _base_state(
        messages=[HumanMessage(content="O que você tem para vender, estranho?")],
        npcs={"Vendedor Misterioso": vendedor},
        active_npc_name="Vendedor Misterioso",
    )

    result = npc_actor_node(state)

    assert result.get("messages"), "npc_actor deve retornar mensagem de diálogo"
    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip(), "diálogo do NPC vazio"
    assert "Vendedor Misterioso" in ai_msg.content, "resposta deve incluir nome do NPC"
    assert _no_fallback(result)


# ---------------------------------------------------------------------------
# Teste 4: loot_node direto
# Geração de tesouro (TREASURE) → ~1 SMART call
# ---------------------------------------------------------------------------
def test_loot_node_direct():
    goblin_morto = {
        "id": "goblin_morto",
        "name": "Goblin",
        "hp": 0, "max_hp": 12,
        "stamina": 0, "mana": 0,
        "defense": 11, "attack_mod": 2,
        "attributes": {"str": 8, "dex": 14, "con": 10, "int": 6, "wis": 8, "cha": 6},
        "abilities": [],
        "status": "morto",
        "active_conditions": [],
        "attacks": [],
    }
    state = _base_state(
        messages=[HumanMessage(content="vasculho o corpo do goblin em busca de itens valiosos")],
        loot_source="TREASURE",
        enemies=[goblin_morto],
    )

    result = loot_node(state)

    assert result.get("messages"), "loot_node deve retornar mensagem"
    ai_msg = result["messages"][-1]
    assert isinstance(ai_msg, AIMessage) and ai_msg.content.strip(), "narrativa de loot vazia"
    assert _no_fallback(result)
