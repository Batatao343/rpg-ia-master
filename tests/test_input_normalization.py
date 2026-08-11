"""Fronteiras de texto livre vindas do LLM: sentinelas, alvo e loot."""

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

import agents.npc as npc_mod
import agents.router as router_mod
from agents.router import RouterDecision, RouteType, dm_router_node
from services.input_normalization import optional_entity_ref


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "   ",
        "null",
        " NULL ",
        "None",
        "nil",
        "N/A",
        "undefined",
        "nenhum",
        "NINGUÉM",
        "ninguem",
    ],
)
def test_optional_entity_ref_normaliza_sentinelas(value):
    assert optional_entity_ref(value) is None


def test_optional_entity_ref_preserva_nome_real_e_remove_espacos():
    assert optional_entity_ref("  A Figura Pálida  ") == "A Figura Pálida"


def test_router_decision_fecha_e_normaliza_loot_context():
    parsed = RouterDecision(
        route=RouteType.LOOT,
        loot_context=" shop ",
        target=None,
        reasoning="comercio",
        confidence=0.9,
    )
    assert parsed.loot_context == "SHOP"

    with pytest.raises(ValidationError):
        RouterDecision(
            route=RouteType.LOOT,
            loot_context="CORPSE",
            target=None,
            reasoning="valor fora do contrato",
            confidence=0.9,
        )


class _DecisionLLM:
    def __init__(self, decision: RouterDecision):
        self.decision = decision

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def invoke(self, _messages):
        return self.decision


def _route(monkeypatch, decision, **state_overrides):
    monkeypatch.setattr(
        router_mod, "get_llm", lambda *_args, **_kwargs: _DecisionLLM(decision)
    )
    state = {
        "messages": [HumanMessage(content="acao")],
        "world": {"current_location": "Ponte"},
        "npcs": {},
        "combat": None,
    }
    state.update(state_overrides)
    return dm_router_node(state)


def test_story_limpa_alvos_residuais(monkeypatch):
    decision = RouterDecision(
        route=RouteType.STORY,
        loot_context=None,
        target="Goblin",
        reasoning="explorar",
        confidence=0.9,
    )
    out = _route(monkeypatch, decision)

    assert out["next"] == RouteType.STORY.value
    assert out["combat_target"] is None
    assert out["active_npc_name"] is None


def test_combate_com_sentinela_recebe_alvo_seguro(monkeypatch):
    decision = RouterDecision(
        route=RouteType.COMBAT,
        loot_context=None,
        target=" NULL ",
        reasoning="ataque sem alvo nomeado",
        confidence=0.7,
    )
    out = _route(monkeypatch, decision)

    assert out["combat_target"] == "Inimigos"
    assert "TARGET_HINT: Inimigos" in out["messages"][0].content


def test_router_npc_ignora_chave_legada_null_e_escolhe_nome_valido(monkeypatch):
    decision = RouterDecision(
        route=RouteType.NPC,
        loot_context=None,
        target="null",
        reasoning="conversar",
        confidence=0.8,
    )
    out = _route(
        monkeypatch,
        decision,
        npcs={"null": {"name": "null"}, "Aria": {"name": "Aria"}},
    )

    assert out["active_npc_name"] == "Aria"


def test_router_npc_sem_alvo_nao_escolhe_conhecido_fora_de_cena(monkeypatch):
    decision = RouterDecision(
        route=RouteType.NPC,
        loot_context=None,
        target=None,
        reasoning="conversar com alguém presente",
        confidence=0.8,
    )
    out = _route(
        monkeypatch,
        decision,
        npcs={"Aria": {"name": "Aria", "in_scene": False}},
    )

    assert out["active_npc_name"] is None


def test_npc_actor_nao_reativa_npc_null_de_save_legado(monkeypatch):
    from services import npc_layers

    monkeypatch.setattr(
        npc_layers, "npcs_in_scene", lambda _state: [" null ", "N/A"]
    )

    def _must_not_generate(*_args, **_kwargs):
        raise AssertionError("sentinela nao pode gerar ou carregar NPC")

    monkeypatch.setattr(npc_mod, "generate_new_npc", _must_not_generate)
    out = npc_mod.npc_actor_node(
        {
            "messages": [HumanMessage(content="Tem alguém aqui?")],
            "active_npc_name": " NULL ",
            "npcs": {"null": {"name": "null", "in_scene": True}},
            "world": {"current_location": "Ponte"},
        }
    )

    assert out["next"] == "storyteller"
    assert "npc_fallback_hint" in out


def test_npc_gerado_materializa_e_persiste_ficha_v4_deterministica(monkeypatch):
    proposed = npc_mod.NPCSchema(
        name="A Figura Pálida",
        role="Oráculo",
        location="Ponte",
        persona="Silenciosa",
        appearance="Manto branco",
        attributes={"str": 99, "dex": 99, "con": 99, "int": 99, "wis": 99, "cha": 99},
        combat_stats={"hp": 9999, "ac": 9999, "attacks": [{"damage": "999d999"}]},
    )

    class _NPCDesigner:
        def with_structured_output(self, *_args, **_kwargs):
            return self

        def invoke(self, _messages):
            return proposed

    persisted = []
    monkeypatch.setattr(npc_mod, "load_npc_db", lambda: {})
    monkeypatch.setattr(npc_mod, "find_existing_entity", lambda *_args: None)
    monkeypatch.setattr(npc_mod, "query_rag", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(npc_mod, "get_llm", lambda *_args, **_kwargs: _NPCDesigner())
    monkeypatch.setattr(npc_mod, "save_npc_template", lambda data: persisted.append(dict(data)))

    out = npc_mod.generate_new_npc("A Figura Pálida")

    assert out["vitalidade"] == out["max_vitalidade"] > 0
    assert out["ferimento_espacos"]["critico"] >= 1
    assert out["tactical_profile"]["priorities"]
    assert out["combat_stats"]["hp"] == out["max_vitalidade"]
    assert out["combat_stats"]["hp"] != 9999
    assert persisted and persisted[-1]["tactical_profile"] == out["tactical_profile"]
    assert persisted[-1]["tactical_archetype"] == out["tactical_archetype"] == "mistico"


def test_cache_npc_v4_preserva_estado_de_combate(monkeypatch):
    cached = {
        "id": "npc_aria",
        "name": "Aria",
        "attributes": {"str": 10},
        "virtudes": {"forca": 1, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 4},
        "vitalidade": 1,
        "max_vitalidade": 8,
        "ferimento_espacos": {"leve": 2, "grave": 1, "critico": 1},
        "ferimentos": {"leve": ["corte"], "grave": [], "critico": []},
        "esquiva": 12,
        "categoria": "padrao",
        "active_conditions": ["abalado"],
        "tactical_profile": {
            "priorities": [{"action": "defender", "when": {"sempre": True}}],
        },
        "status": "ativo",
        "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
    }
    monkeypatch.setattr(npc_mod, "load_npc_db", lambda: {"npc_aria": cached})
    monkeypatch.setattr(
        npc_mod, "find_existing_entity", lambda *_args, **_kwargs: "npc_aria"
    )

    def _must_not_save(_data):
        raise AssertionError("cache v4 completo nao deve ser rematerializado")

    monkeypatch.setattr(npc_mod, "save_npc_template", _must_not_save)
    out = npc_mod.generate_new_npc("Aria")

    assert out["vitalidade"] == 1
    assert out["ferimentos"]["leve"] == ["corte"]
    assert out["active_conditions"] == ["abalado"]
